"""Local STT via faster-whisper (OpenAI Whisper, offline)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from backend.config import get_settings

logger = logging.getLogger(__name__)

_model = None


class LocalSTTError(RuntimeError):
    """Local Whisper error."""


def _get_model():
    global _model
    if _model is not None:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise LocalSTTError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    settings = get_settings()
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
    return _model


def _minimal_wav_bytes() -> bytes:
    """~0.25 c тишины — прогрев декодера без HF."""
    import struct

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


def transcribe_audio_local(
    audio: bytes,
    *,
    language: str = "ru",
    filename: str | None = None,
) -> str:
    if not audio:
        raise LocalSTTError("Empty audio payload.")

    model = _get_model()
    suffix = _audio_suffix(audio, filename)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio)
        path = Path(tmp.name)

    try:
        segments, _info = model.transcribe(
            str(path),
            language=language,
            beam_size=1,
            vad_filter=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        path.unlink(missing_ok=True)

    if not text:
        logger.warning("Whisper empty transcript (suffix=%s bytes=%s)", suffix, len(audio))
        return ""
    logger.info("Local Whisper ok chars=%s", len(text))
    return text
