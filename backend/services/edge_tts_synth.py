"""Нейронный TTS через edge-tts (Microsoft) — запасной голос, если SpeechKit недоступен."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Живой женский голос RU (не SAPI-робот)
DEFAULT_VOICE = "ru-RU-SvetlanaNeural"


async def synthesize_mp3(text: str, *, voice: str = DEFAULT_VOICE) -> bytes:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("edge-tts not installed") from exc

    communicate = edge_tts.Communicate((text or "").strip() or ".", voice=voice)
    chunks: list[bytes] = []
    async for item in communicate.stream():
        if item.get("type") == "audio" and item.get("data"):
            chunks.append(item["data"])
    audio = b"".join(chunks)
    if not audio:
        raise RuntimeError("edge-tts returned empty audio")
    logger.info("edge-tts ok voice=%s bytes=%s", voice, len(audio))
    return audio
