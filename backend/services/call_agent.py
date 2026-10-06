"""Unified call agent: local (default) or yandex."""

from __future__ import annotations

import logging

from backend.config import Settings, get_settings
from backend.schemas import CallRequest, CallResponse
from backend.services.local_llm import process_call_with_ollama
from backend.services.yandex_llm import process_call_with_yandex

logger = logging.getLogger(__name__)


async def process_incoming_call(
    request: CallRequest,
    settings: Settings | None = None,
) -> CallResponse:
    settings = settings or get_settings()
    provider = (settings.llm_provider or "local").strip().lower()
    if provider == "yandex":
        logger.info("LLM provider=yandex")
        return await process_call_with_yandex(request, settings)
    logger.info("LLM provider=local model=%s", settings.ollama_model)
    return await process_call_with_ollama(request, settings)
