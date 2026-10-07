// Перебивание и конец фразы в живом звонке: модуль backend/static/live_vad.js без браузера.
// Запуск: node tests/barge_in_check.js (или через tests/test_barge_in.py)
"use strict";
const path = require("path");
const { createVad, rmsOf } = require(path.join(__dirname, "..", "backend", "static", "live_vad.js"));

const FRAME_MS = (4096 / 48000) * 1000; // ScriptProcessor 4096 @ 48 кГц ≈ 85 мс
let failed = 0;

function check(name, ok, detail) {
  if (ok) console.log("OK   " + name);
  else { failed++; console.log("FAIL " + name + (detail !== undefined ? " — " + JSON.stringify(detail) : "")); }
}

// segments: [{ level, ms, mode }] → события с моментом и номером кадра
function play(vad, segments, opts = {}) {
  const frameMs = opts.frameMs || FRAME_MS;
  let now = opts.startAt || 0, idx = 0;
  const events = [];
  for (const seg of segments) {
    const frames = Math.round(seg.ms / frameMs);
    for (let i = 0; i < frames; i++, idx++, now += frameMs) {
      const level = typeof seg.level === "function" ? seg.level(idx) : seg.level;
      const frame = new Float32Array([idx, level]); // idx — метка кадра для проверки preroll
      const ev = vad.feed(frame, level, frameMs, seg.mode || "listen", now);
      if (ev) events.push(Object.assign({ at: Math.round(now), frame: idx }, ev));
    }
  }
  return { events, now };
}
const types = (evs) => evs.map((e) => e.type + (e.bargeIn ? "(barge)" : ""));

const QUIET = 0.002, ECHO = 0.035;
// Речь: громкость гуляет по слогам; гул поезда/вентилятора почти ровный
const VOICE = (i) => 0.15 * (0.7 + 0.3 * Math.sin(i * 0.9));
const NOISE = (i) => 0.02 * (1 + 0.05 * Math.sin(i * 2.1));
const VOICE_PEAK = 0.15;

console.log("=== обычная фраза ===");
{
  const vad = createVad();
  const { events } = play(vad, [{ level: QUIET, ms: 1000 }, { level: VOICE, ms: 1200 }, { level: QUIET, ms: 1200 }]);
  check("фраза → начало и конец", types(events).join() === "speech_start,utterance", types(events));
  const utt = events.find((e) => e.type === "utterance");
  check("фраза ≈ 1.2 с голоса", utt && utt.voicedMs >= 1100 && utt.voicedMs <= 1700, utt && utt.voicedMs);
  const first = utt && utt.chunks[0][0];
  const voiceStart = Math.round(1000 / FRAME_MS);
  check("preroll: начало слова не потеряно", first !== undefined && first < voiceStart, { first, voiceStart });
  check("после фразы детектор снова ждёт", !vad.speaking);
}

console.log("\n=== щелчки и кашель ===");
{
  const vad = createVad();
  const { events } = play(vad, [{ level: QUIET, ms: 800 }, { level: VOICE_PEAK, ms: 85 }, { level: QUIET, ms: 1500 }]);
  check("одиночный щелчок игнорируется", events.length === 0, types(events));
}
{
  const vad = createVad({ PREROLL_FRAMES: 2 });
  const { events } = play(vad, [{ level: QUIET, ms: 800 }, { level: VOICE_PEAK, ms: 170 }, { level: QUIET, ms: 1500 }]);
  check("короткий кашель → too_short, не уходит в STT", types(events).join() === "speech_start,too_short", types(events));
}

console.log("\n=== эхо агента НЕ перебивает ===");
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }]);
  vad.agentStarted(1000);
  const { events } = play(vad, [{ level: ECHO, ms: 4000, mode: "agent" }], { startAt: 1000 });
  check("эхо динамика 4 с → без перебивания", events.length === 0, types(events));
}
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }]);
  vad.agentStarted(1000);
  const { events } = play(vad, [
    { level: QUIET, ms: 1000, mode: "agent" },
    { level: 0.09, ms: 170, mode: "agent" },
    { level: QUIET, ms: 1000, mode: "agent" },
  ], { startAt: 1000 });
  check("громкий всплеск 0.17 с (ударение в речи агента) → без перебивания", events.length === 0, types(events));
}
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }]);
  vad.agentStarted(1000);
  const echo = (i) => 0.06 * (0.6 + 0.4 * Math.sin(i * 1.7));
  const { events } = play(vad, [{ level: echo, ms: 5000, mode: "agent" }], { startAt: 1000 });
  check("громкое эхо речи агента 5 с → без перебивания", events.length === 0, types(events));
}
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }]);
  const floorBefore = vad.noiseFloor;
  vad.agentStarted(1000);
  play(vad, [{ level: 0.03, ms: 5000, mode: "agent" }], { startAt: 1000 });
  check("эхо не поднимает уровень шума", Math.abs(vad.noiseFloor - floorBefore) < 1e-9, { floorBefore, after: vad.noiseFloor });
}

console.log("\n=== звонящий перебивает ===");
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }]);
  vad.agentStarted(1000);
  const { events } = play(vad, [
    { level: ECHO, ms: 1500, mode: "agent" },
    { level: VOICE, ms: 900, mode: "agent" },
    { level: QUIET, ms: 1200, mode: "listen" },
  ], { startAt: 1000 });
  check("громкий голос поверх агента → перебивание", types(events).join() === "speech_start(barge),utterance", types(events));
  const start = events[0];
  const voiceAt = 1000 + 1500;
  check("перебивание срабатывает за ≤0.5 с", start && start.at - voiceAt <= 500, start && start.at - voiceAt);
  const utt = events.find((e) => e.type === "utterance");
  check("фраза после перебивания уходит в STT", utt && utt.voicedMs >= 700, utt && utt.voicedMs);
}
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }]);
  vad.agentStarted(1000);
  const { events } = play(vad, [{ level: VOICE, ms: 600, mode: "agent" }, { level: QUIET, ms: 600, mode: "agent" }], { startAt: 1000 });
  check("первые 0.7 с озвучки перебить нельзя (щелчок старта звука)", events.length === 0, types(events));
}
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }]);
  vad.agentStarted(1000);
  const { events } = play(vad, [{ level: VOICE, ms: 1500, mode: "agent" }], { startAt: 1000 });
  const start = events.find((e) => e.type === "speech_start");
  check("голос сразу после старта → перебивание после паузы 0.7 с", start && start.bargeIn && start.at >= 1700, start);
}
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 800 }, { level: VOICE, ms: 120 }]);
  vad.agentStarted(1000);
  const { events } = play(vad, [{ level: VOICE, ms: 170, mode: "agent" }, { level: QUIET, ms: 800, mode: "agent" }], { startAt: 1700 });
  check("кадры голоса до озвучки не засчитываются в перебивание", events.length === 0, types(events));
}
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 1000 }], { frameMs: (4096 / 44100) * 1000 });
  vad.agentStarted(1000);
  const { events } = play(vad, [{ level: VOICE, ms: 800, mode: "agent" }], { startAt: 1800, frameMs: (4096 / 44100) * 1000 });
  check("44.1 кГц: перебивание тоже работает", events.length && events[0].bargeIn, types(events));
}

console.log("\n=== шумно (поезд, улица) ===");
{
  const vad = createVad();
  const { events } = play(vad, [{ level: QUIET, ms: 1000 }, { level: NOISE, ms: 5000 }]);
  const noise = events.find((e) => e.type === "noise");
  check("резко начавшийся гул 5 с → в STT ничего не уходит", !events.some((e) => e.type === "utterance"), types(events));
  check("гул опознан как шум за ≤2 с", noise && noise.at - 1000 <= 2000, noise && noise.at - 1000);
  check("после гула больше не срабатывает", events.filter((e) => e.type === "speech_start").length === 1, types(events));
  check("порог подстроился под шум", vad.noiseFloor > 0.015, vad.noiseFloor);
  const after = play(vad, [{ level: VOICE, ms: 1200 }, { level: NOISE, ms: 1200 }], { startAt: 6000 });
  check("голос поверх гула → фраза в STT", types(after.events).join() === "speech_start,utterance", types(after.events));
}
{
  const vad = createVad();
  const { events } = play(vad, [{ level: NOISE, ms: 1000 }, { level: VOICE, ms: 2500 }, { level: NOISE, ms: 3000 }]);
  const utt = events.find((e) => e.type === "utterance");
  check("гул шёл с начала: фраза всё равно уходит в STT", !!utt, types(events));
  check("гул после фразы отрезан, речь целиком", utt && utt.voicedMs >= 2300 && utt.chunks.length * FRAME_MS <= 4200,
    utt && { voicedMs: utt.voicedMs, ms: Math.round(utt.chunks.length * FRAME_MS) });
  const endAt = 1000 + 2500;
  check("конец фразы в шуме — не позже 2 с после последнего слова", utt && utt.at - endAt <= 2000, utt && utt.at - endAt);
}

console.log("\n=== длинная речь ===");
{
  const vad = createVad();
  const { events } = play(vad, [{ level: QUIET, ms: 500 }, { level: VOICE, ms: 27000 }]);
  const utt = events.find((e) => e.type === "utterance");
  check("живая речь не считается гулом", !events.some((e) => e.type === "noise"), types(events));
  check("монолог режется на ≤25 с (лимит SpeechKit)", utt && utt.voicedMs <= 25100, utt && utt.voicedMs);
}

console.log("\n=== сброс ===");
{
  const vad = createVad();
  play(vad, [{ level: QUIET, ms: 500 }, { level: VOICE, ms: 500 }]);
  const wasSpeaking = vad.speaking;
  vad.reset();
  const { events } = play(vad, [{ level: QUIET, ms: 1500 }], { startAt: 1000 });
  check("reset (текстовая реплика) обрывает недосказанную фразу", wasSpeaking && !vad.speaking && events.length === 0, types(events));
}
check("rmsOf считает уровень", Math.abs(rmsOf(new Float32Array([0.5, -0.5])) - 0.5) < 1e-9);

console.log(failed ? `\nFAILED: ${failed}` : "\nALL BARGE-IN CHECKS OK");
process.exit(failed ? 1 : 0);
