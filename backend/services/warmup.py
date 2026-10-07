"""Лёгкий прогрев при старте. Ollama/Whisper не трогаем (стек = Yandex)."""

from __future__ import annotations

import logging

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def warmup_demo_stack(settings: Settings | None = None) -> dict[str, str]:
    settings = settings or get_settings()
    status: dict[str, str] = {
        "whisper": "skip",
        "ollama": "skip",
        "greeting": "skip",
        "stack": "yandex",
    }

    stt = (settings.stt_provider or "").strip().lower()
    llm = (settings.llm_provider or "").strip().lower()

    # Только если явно вернули local STT — тогда Whisper
    if stt == "local":
        try:
            from backend.services.local_stt import preload_whisper_model, warmup_whisper_decode
            import asyncio

            await asyncio.to_thread(preload_whisper_model)
            await asyncio.to_thread(warmup_whisper_decode)
            status["whisper"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["whisper"] = f"fail:{exc!s}"[:120]
            logger.warning("Warmup Whisper failed: %s", exc)
    else:
        status["whisper"] = "skip:stt=yandex"

    if llm == "local":
        status["ollama"] = "skip:not-warmed"
    else:
        status["ollama"] = "skip:llm=yandex"

    try:
        from backend.services.greeting_audio import ensure_greeting_wav
        import asyncio

        status["greeting"] = await asyncio.to_thread(ensure_greeting_wav)
    except Exception as exc:  # noqa: BLE001
        status["greeting"] = f"fail:{exc!s}"[:120]

    yandex_ok = bool(settings.yc_folder_id and settings.yc_api_key)
    status["yandex"] = "ok" if yandex_ok else "fail:missing YC_FOLDER_ID/YC_API_KEY"
    return status
