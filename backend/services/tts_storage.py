"""Local TTS cache for hackathon demo (not for production telephony).

По ТЗ в проде ответ агента стримится в голосовой канал в реальном времени
и на диск оператора не кладётся как «файлы разговора».
Здесь `data/tts/` — только демо: скачать/прослушать ответ в Swagger.
Папка уже под `.gitignore` через `data/`.
"""

from __future__ import annotations

from pathlib import Path

from backend.config import ROOT_DIR

TTS_DIR = ROOT_DIR / "data" / "tts"


def ensure_tts_dir() -> Path:
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    return TTS_DIR


def audio_path_for_call(call_id: int) -> Path:
    return ensure_tts_dir() / f"call_{call_id}.ogg"


def audio_url_for_call(call_id: int) -> str:
    return f"/api/v1/calls/{call_id}/audio"


def save_call_audio(call_id: int, audio: bytes) -> Path:
    path = audio_path_for_call(call_id)
    path.write_bytes(audio)
    return path
