"""Заранее озвученное приветствие (CJM: disclosure) — фронт играет, пока идёт STT+LLM."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.config import ROOT_DIR, get_settings
from backend.services.yandex_llm import AI_DISCLOSURE_PREFIX

logger = logging.getLogger(__name__)

GREETING_DIR = ROOT_DIR / "data" / "tts"
GREETING_NAME = "greeting_disclosure.wav"
GREETING_TEXT = (
    f"{AI_DISCLOSURE_PREFIX}"
    "Здравствуйте! Я ИИ-помощник Ивана Петрова. Слушаю вас."
)


def greeting_path() -> Path:
    return GREETING_DIR / GREETING_NAME


def greeting_audio_url() -> str | None:
    path = greeting_path()
    if path.is_file() and path.stat().st_size > 44:
        return f"/api/v1/tts/{GREETING_NAME}"
    return None


def ensure_greeting_wav() -> str:
    """Синтез один раз при warmup. Возвращает status ok|skip|fail:..."""
    GREETING_DIR.mkdir(parents=True, exist_ok=True)
    path = greeting_path()
    if path.is_file() and path.stat().st_size > 44:
        logger.info("Greeting audio already cached: %s", path.name)
        return "ok:cached"
    try:
        from backend.services.local_tts import synthesize_wav_local

        audio = synthesize_wav_local(GREETING_TEXT)
        path.write_bytes(audio)
        logger.info("Greeting audio baked bytes=%s", len(audio))
        return "ok:baked"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Greeting bake failed: %s", exc)
        return f"fail:{exc!s}"[:100]
