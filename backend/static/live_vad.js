// Детектор речи живого звонка: конец фразы по паузе + перебивание агента.
// Без DOM и микрофона — тот же код гоняет tests/barge_in_check.js под Node.
(function (root) {
  "use strict";

  const DEFAULTS = {
    END_SILENCE_MS: 800,      // столько тишины = конец фразы
    MIN_SPEECH_MS: 350,       // короче — щелчок/кашель, не отправляем
    MAX_UTTERANCE_MS: 25000,  // лимит SpeechKit ~30 с
    PREROLL_FRAMES: 4,        // захватываем начало слова до срабатывания
    BASE_MIN_LEVEL: 0.012,
    // Перебивание агента: эхо динамика громче тишины, поэтому нужен голос громче и дольше
    BARGE_IN_GRACE_MS: 700,
    BARGE_IN_GAIN: 4,
    BARGE_IN_MIN_LEVEL: 0.04,
    BARGE_IN_MS: 300,
    // Ровный гул (поезд, вентилятор) резко начался — сперва похож на речь. У речи громкость
    // скачет по слогам, у гула нет: ровный уровень дольше окна = шум, порог поднимаем под него
    STEADY_WINDOW_MS: 1500,
    STEADY_CV: 0.15,
    TAIL_KEEP_MS: 300,        // хвост после последнего слова, чтобы не срезать окончание
  };

  function rmsOf(frame) {
    let sum = 0;
    for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
    return Math.sqrt(sum / Math.max(1, frame.length));
  }

  function createVad(overrides) {
    const cfg = Object.assign({}, DEFAULTS, overrides || {});
    let noiseFloor = 0.004, utter = [], preroll = [];
    let speechMs = 0, silenceMs = 0, voicedFrames = 0, agentStartedAt = -Infinity, speaking = false;
    let recent = [], utterRms = [];

    function reset() {
      utter = []; utterRms = []; preroll = []; speechMs = 0; silenceMs = 0; voicedFrames = 0; speaking = false;
      recent = [];
    }

    function steadyLevel(frameMs) {
      const need = Math.ceil(cfg.STEADY_WINDOW_MS / frameMs);
      if (recent.length < need) return null;
      const mean = recent.reduce((a, b) => a + b, 0) / recent.length;
      const variance = recent.reduce((a, b) => a + (b - mean) * (b - mean), 0) / recent.length;
      return mean > 0 && Math.sqrt(variance) / mean < cfg.STEADY_CV ? mean : null;
    }

    // mode: "listen" — ждём звонящего, "agent" — агент говорит (перебивание по строгому порогу).
    // Возвращает null или событие: speech_start {bargeIn}, too_short, noise {level},
    // utterance {chunks, voicedMs}.
    function feed(frame, rms, frameMs, mode, now) {
      recent.push(rms);
      if (recent.length > Math.ceil(cfg.STEADY_WINDOW_MS / frameMs)) recent.shift();
      const agentTalking = mode === "agent" && !speaking;
      if (agentTalking && now - agentStartedAt < cfg.BARGE_IN_GRACE_MS) return null;
      const baseThr = Math.max(noiseFloor * 3, cfg.BASE_MIN_LEVEL);
      const thr = agentTalking ? Math.max(baseThr * cfg.BARGE_IN_GAIN, cfg.BARGE_IN_MIN_LEVEL) : baseThr;

      if (!speaking) {
        const need = agentTalking ? Math.max(2, Math.ceil(cfg.BARGE_IN_MS / frameMs)) : 2;
        if (!agentTalking && rms < thr) noiseFloor = noiseFloor * 0.97 + rms * 0.03;
        preroll.push(frame);
        if (preroll.length > cfg.PREROLL_FRAMES) preroll.shift();
        voicedFrames = rms > thr ? voicedFrames + 1 : 0;
        if (voicedFrames < need) return null;
        speaking = true;
        utter = preroll.slice(); preroll = [];
        utterRms = recent.slice(-utter.length);
        speechMs = frameMs * utter.length; silenceMs = 0;
        return { type: "speech_start", bargeIn: agentTalking };
      }

      utter.push(frame); speechMs += frameMs;
      utterRms.push(rms);
      const steady = steadyLevel(frameMs);
      if (steady !== null) {
        // Речь до гула — в STT (паузы в шуме не будет), сам гул отбрасываем
        noiseFloor = steady;
        const head = Math.max(0, utter.length - Math.ceil(cfg.STEADY_WINDOW_MS / frameMs));
        const voicedMs = utterRms.slice(0, head).filter((r) => r > steady * 2).length * frameMs;
        const chunks = utter.slice(0, head + Math.round(cfg.TAIL_KEEP_MS / frameMs));
        reset();
        return voicedMs >= cfg.MIN_SPEECH_MS ? { type: "utterance", chunks, voicedMs } : { type: "noise", level: steady };
      }
      silenceMs = rms < thr * 0.6 ? silenceMs + frameMs : 0;
      if (silenceMs < cfg.END_SILENCE_MS && speechMs < cfg.MAX_UTTERANCE_MS) return null;
      const voicedMs = speechMs - silenceMs;
      const chunks = utter;
      reset();
      return voicedMs < cfg.MIN_SPEECH_MS ? { type: "too_short", voicedMs } : { type: "utterance", chunks, voicedMs };
    }

    return {
      cfg,
      feed,
      reset,
      agentStarted(now) { agentStartedAt = now; voicedFrames = 0; preroll = []; },
      get noiseFloor() { return noiseFloor; },
      get speaking() { return speaking; },
    };
  }

  const api = { createVad, rmsOf, DEFAULTS };
  root.LiveVad = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
