"""Local TTS cache for hackathon demo (not for production telephony).

По ТЗ в проде ответ агента стримится в голосовой канал.
Здесь data/tts/ — только демо для Swagger.
"""

from __future__ import annotations

from pathlib import Path

from backend.config import ROOT_DIR

TTS_DIR = ROOT_DIR / "data" / "tts"


def ensure_tts_dir() -> Path:
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    return TTS_DIR


def audio_path_for_call(call_id: int, ext: str = "wav") -> Path:
    safe = ext.lstrip(".").lower() or "wav"
    if safe not in {"wav", "ogg"}:
        safe = "wav"
    return ensure_tts_dir() / f"call_{call_id}.{safe}"


def audio_url_for_call(call_id: int) -> str:
    return f"/api/v1/calls/{call_id}/audio"


def save_call_audio(call_id: int, audio: bytes, ext: str = "wav") -> Path:
    path = audio_path_for_call(call_id, ext=ext)
    path.write_bytes(audio)
    return path


def find_call_audio(call_id: int) -> Path | None:
    for ext in ("wav", "ogg"):
        path = audio_path_for_call(call_id, ext=ext)
        if path.is_file():
            return path
    return None
