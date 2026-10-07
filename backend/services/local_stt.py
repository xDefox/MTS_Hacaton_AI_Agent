"""Local STT via faster-whisper (OpenAI Whisper, offline).

Оптимизировано под шумную линию (улица, поезд, эхо): base-модель,
VAD с запасом по краям, нормализация громкости, retry без VAD.
"""

from __future__ import annotations

import logging
import struct
import tempfile
import wave
from pathlib import Path

from backend.config import get_settings

logger = logging.getLogger(__name__)

_model = None
_model_key: str | None = None

# Контекст телефона — меньше «галлюцинаций» Whisper на шуме
_PHONE_PROMPT_RU = (
    "Звонок на русском языке секретарю компании. "
    "Разборчивая речь абонента, возможны помехи линии."
)


class LocalSTTError(RuntimeError):
    """Local Whisper error."""


def _get_model():
    global _model, _model_key
    settings = get_settings()
    key = f"{settings.whisper_model_size}:{settings.whisper_device}:{settings.whisper_compute_type}"
    if _model is not None and _model_key == key:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise LocalSTTError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    logger.info(
        "Loading Whisper size=%s device=%s compute=%s",
        settings.whisper_model_size,
        settings.whisper_device,
        settings.whisper_compute_type,
    )
    kwargs: dict = {
        "device": settings.whisper_device,
        "compute_type": settings.whisper_compute_type,
    }
    if settings.whisper_cpu_threads > 0:
        kwargs["cpu_threads"] = settings.whisper_cpu_threads
    _model = WhisperModel(settings.whisper_model_size, **kwargs)
    _model_key = key
    return _model


def _minimal_wav_bytes() -> bytes:
    """~0.25 c тишины — прогрев декодера без HF."""
    rate, duration = 16000, 0.25
    n = int(rate * duration)
    data = b"\x00\x00" * n
    block = 36 + len(data)
    return (
        b"RIFF"
        + struct.pack("<I", block)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )


def preload_whisper_model() -> None:
    """Вызвать при старте API — иначе первый /process_call_voice ждёт загрузку модели."""
    _get_model()


def warmup_whisper_decode() -> None:
    transcribe_audio_local(_minimal_wav_bytes(), language="ru", filename="warmup.wav")


def _audio_suffix(audio: bytes, filename: str | None) -> str:
    if len(audio) >= 4 and audio[:4] == b"RIFF":
        return ".wav"
    if len(audio) >= 4 and audio[:4] == b"OggS":
        return ".ogg"
    if audio[:3] == b"ID3" or (len(audio) >= 2 and audio[:2] in (b"\xff\xfb", b"\xff\xf3")):
        return ".mp3"
    if len(audio) >= 8 and audio[4:8] == b"ftyp":
        return ".m4a"
    if len(audio) >= 4 and audio[:4] == b"\x1aE\xdf\xa3":
        return ".webm"
    name = (filename or "").lower()
    for ext in (".wav", ".ogg", ".opus", ".webm", ".mp3", ".m4a", ".flac"):
        if name.endswith(ext):
            return ext
    return ".wav"


def _peak_normalize_wav(path: Path) -> Path | None:
    """Поднять тихую речь (поезд/далекий микрофон) до −1 dBFS по пику."""
    try:
        with wave.open(str(path), "rb") as wf:
            nch, sw, rate, nframes, _, _ = wf.getparams()
            if sw != 2:
                return None
            frames = wf.readframes(nframes)
        if not frames:
            return None
        samples = list(struct.unpack(f"<{len(frames) // 2}h", frames))
        if nch > 1:
            # mono = среднее каналов
            mono = [
                int(sum(samples[i : i + nch]) / nch)
                for i in range(0, len(samples), nch)
            ]
        else:
            mono = samples
        peak = max(abs(s) for s in mono) or 1
        # Цель ~90% int16 range
        gain = min(8.0, (30000.0 / peak))
        if gain < 1.05:
            return None
        out = [max(-32768, min(32767, int(s * gain))) for s in mono]
        out_path = path.with_name(path.stem + "_norm.wav")
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(struct.pack(f"<{len(out)}h", *out))
        logger.info("STT normalize gain=%.2f peak=%s -> %s", gain, peak, out_path.name)
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.debug("STT normalize skip: %s", exc)
        return None


def _transcribe_once(
    model,
    path: Path,
    *,
    language: str,
    beam_size: int,
    vad_filter: bool,
    initial_prompt: str,
) -> tuple[str, float]:
    vad_params = None
    if vad_filter:
        # Ниже порог + pad — лучше держит речь на фоне шума поезда/улицы
        vad_params = {
            "threshold": 0.28,
            "min_speech_duration_ms": 120,
            "min_silence_duration_ms": 350,
            "speech_pad_ms": 450,
        }
    segments, _info = model.transcribe(
        str(path),
        language=language,
        beam_size=beam_size,
        best_of=1,
        vad_filter=vad_filter,
        vad_parameters=vad_params,
        condition_on_previous_text=False,
        without_timestamps=True,
        initial_prompt=initial_prompt,
        temperature=0.0,
    )
    parts: list[str] = []
    probs: list[float] = []
    for seg in segments:
        t = (seg.text or "").strip()
        if t:
            parts.append(t)
            if getattr(seg, "avg_logprob", None) is not None:
                probs.append(float(seg.avg_logprob))
    text = " ".join(parts).strip()
    conf = sum(probs) / len(probs) if probs else 0.0
    return text, conf


def transcribe_audio_local(
    audio: bytes,
    *,
    language: str = "ru",
    filename: str | None = None,
) -> str:
    if not audio:
        raise LocalSTTError("Empty audio payload.")

    settings = get_settings()
    model = _get_model()
    suffix = _audio_suffix(audio, filename)
    beam = max(1, int(settings.whisper_beam_size))
    use_vad = bool(settings.whisper_vad_filter)
    prompt = (settings.whisper_initial_prompt or _PHONE_PROMPT_RU).strip()

    raw_path: Path | None = None
    norm_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio)
            raw_path = Path(tmp.name)

        work = raw_path
        if suffix == ".wav" and settings.whisper_normalize:
            norm_path = _peak_normalize_wav(raw_path)
            if norm_path is not None:
                work = norm_path

        text, conf = _transcribe_once(
            model,
            work,
            language=language,
            beam_size=beam,
            vad_filter=use_vad,
            initial_prompt=prompt,
        )
        # Пусто на шуме — повторяем без VAD (часто VAD съедает речь)
        if not text and use_vad:
            logger.info("STT empty with VAD — retry without VAD")
            text, conf = _transcribe_once(
                model,
                work,
                language=language,
                beam_size=beam,
                vad_filter=False,
                initial_prompt=prompt,
            )
    finally:
        if raw_path is not None:
            raw_path.unlink(missing_ok=True)
        if norm_path is not None:
            norm_path.unlink(missing_ok=True)

    if not text:
        logger.warning("Whisper empty transcript (suffix=%s bytes=%s)", suffix, len(audio))
        return ""
    logger.info(
        "Local Whisper ok chars=%s conf_logprob=%.3f model=%s vad=%s beam=%s",
        len(text),
        conf,
        settings.whisper_model_size,
        use_vad,
        beam,
    )
    return text
