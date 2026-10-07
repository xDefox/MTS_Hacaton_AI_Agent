"""Прогрев Whisper + Ollama при старте (первый голосовой запрос иначе «висит» минуту)."""

from __future__ import annotations

import asyncio
import logging

import httpx

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

async def warmup_demo_stack(settings: Settings | None = None) -> dict[str, str]:
    settings = settings or get_settings()
    status: dict[str, str] = {"whisper": "skip", "ollama": "skip", "greeting": "skip"}

    try:
        from backend.services.local_stt import preload_whisper_model, warmup_whisper_decode

        await asyncio.to_thread(preload_whisper_model)
        await asyncio.to_thread(warmup_whisper_decode)
        status["whisper"] = "ok"
        logger.info("Warmup: Whisper loaded (%s)", settings.whisper_model_size)
    except Exception as exc:  # noqa: BLE001
        status["whisper"] = f"fail:{exc!s}"[:120]
        logger.warning("Warmup Whisper failed: %s", exc)

    try:
        from backend.services.greeting_audio import ensure_greeting_wav

        status["greeting"] = await asyncio.to_thread(ensure_greeting_wav)
    except Exception as exc:  # noqa: BLE001
        status["greeting"] = f"fail:{exc!s}"[:120]

    if (settings.llm_provider or "local").strip().lower() != "local":
        return status

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    # Прогрев тем же format=json + чуть длиннее ответ — ближе к боевому вызову
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {
                "role": "user",
                "content": (
                    'Ответь JSON: {"agent_response":"ок","is_critical":false,'
                    '"priority":"low","intent":"other","action_required":"continue_dialog",'
                    '"summary":"прогрев","caller_name":"","recommended_next_step":"готово"}'
                ),
            }
        ],
        "stream": False,
        "format": "json",
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "num_predict": settings.ollama_lite_num_predict,
            "num_ctx": settings.ollama_lite_num_ctx,
            "temperature": 0.0,
        },
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
