"""Local TTS via Windows SAPI / pyttsx3 (offline, no cloud)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_tts_engine = None


class LocalTTSError(RuntimeError):
    """Local TTS error."""


def synthesize_wav_local(text: str) -> bytes:
    """Synthesize speech to WAV bytes (demo playback)."""
    if not (text or "").strip():
        raise LocalTTSError("Empty text for TTS.")

    try:
        import pyttsx3
    except ImportError as exc:
        raise LocalTTSError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

    global _tts_engine
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = Path(tmp.name)

    if _tts_engine is None:
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 190)
        for voice in _tts_engine.getProperty("voices") or []:
            name = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
            if "ru" in name or "russian" in name or "irina" in name:
                _tts_engine.setProperty("voice", voice.id)
                break

    engine = _tts_engine
    engine.save_to_file(text, str(path))
    engine.runAndWait()

    if not path.is_file() or path.stat().st_size < 44:
        path.unlink(missing_ok=True)
        raise LocalTTSError("Local TTS produced empty audio.")

    data = path.read_bytes()
    path.unlink(missing_ok=True)
    logger.info("Local TTS ok bytes=%s", len(data))
    return data
