"""Прогрев Whisper + Ollama при старте (первый голосовой запрос иначе «висит» минуту)."""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

async def warmup_demo_stack(settings: Settings | None = None) -> dict[str, str]:
    settings = settings or get_settings()
    status: dict[str, str] = {"whisper": "skip", "ollama": "skip"}

    try:
        from backend.services.local_stt import preload_whisper_model, warmup_whisper_decode

        await asyncio.to_thread(preload_whisper_model)
        await asyncio.to_thread(warmup_whisper_decode)
        status["whisper"] = "ok"
        logger.info("Warmup: Whisper loaded (%s)", settings.whisper_model_size)
    except Exception as exc:  # noqa: BLE001
        status["whisper"] = f"fail:{exc!s}"[:120]
        logger.warning("Warmup Whisper failed: %s", exc)

    if (settings.llm_provider or "local").strip().lower() != "local":
        return status

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": "ответь одним словом: ок"}],
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": {"num_predict": 16, "num_ctx": 512},
    }
    try:
        timeout = httpx.Timeout(connect=10.0, read=settings.ollama_timeout_sec, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            status["ollama"] = f"fail:HTTP {resp.status_code}"
        else:
            status["ollama"] = "ok"
            logger.info("Warmup: Ollama model hot (%s)", settings.ollama_model)
    except Exception as exc:  # noqa: BLE001
        status["ollama"] = f"fail:{exc!s}"[:120]
        logger.warning("Warmup Ollama failed: %s", exc)

    return status
