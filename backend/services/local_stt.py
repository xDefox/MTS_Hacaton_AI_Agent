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
    _model = WhisperModel(
        settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    return _model


def transcribe_audio_local(audio: bytes, *, language: str = "ru") -> str:
    if not audio:
        raise LocalSTTError("Empty audio payload.")

    model = _get_model()
    # RIFF/WAVE → .wav, иначе пробуем как контейнер (.ogg / generic)
    suffix = ".wav" if audio[:4] == b"RIFF" else ".ogg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio)
        path = Path(tmp.name)

    try:
        segments, _info = model.transcribe(str(path), language=language, beam_size=1)
        text = " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        path.unlink(missing_ok=True)

    if not text:
        raise LocalSTTError("Whisper returned empty transcript.")
    logger.info("Local Whisper ok chars=%s", len(text))
    return text
