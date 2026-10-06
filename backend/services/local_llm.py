"""Local LLM via Ollama (no external cloud API)."""

from __future__ import annotations

import logging
import re

import httpx

from backend.config import Settings, get_settings
from backend.prompts.system_ivan import build_system_prompt
from backend.schemas import CallRequest, CallResponse
from backend.services.yandex_llm import (
    _build_messages,
    _fallback_response,
    _guard_non_business_escalation,
    _parse_output,
    ensure_ai_disclosure,
)

logger = logging.getLogger(__name__)


class LocalLLMError(RuntimeError):
    """Ollama / local model error."""


def _ollama_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("text") or m.get("content") or ""
        if role == "system":
            out.append({"role": "system", "content": content})
        elif role == "assistant":
            out.append({"role": "assistant", "content": content})
        else:
            out.append({"role": "user", "content": content})
    return out


def _extract_json_text(raw: str) -> str:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        return match.group(0)
    return cleaned


async def process_call_with_ollama(
    request: CallRequest,
    settings: Settings | None = None,
) -> CallResponse:
    settings = settings or get_settings()
    system_prompt = build_system_prompt(settings)
    system_prompt = (
        system_prompt
        + "\n\nCRITICAL: Reply with ONE JSON object only. No markdown, no commentary."
    )
    messages = _build_messages(request, system_prompt)
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": _ollama_messages(messages),
        "stream": False,
        "format": "json",
        "options": {"temperature": settings.ollama_temperature},
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout_sec) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            raise LocalLLMError(f"Ollama HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        raw = (data.get("message") or {}).get("content") or ""
        parsed = _parse_output(_extract_json_text(raw))
        caller_name = parsed.caller_name.strip() or None
        response = CallResponse(
            agent_response=ensure_ai_disclosure(parsed.agent_response),
            is_critical=parsed.is_critical,
            priority=parsed.priority,
            intent=parsed.intent,
            action_required=parsed.action_required,
            summary=parsed.summary,
            caller_name=caller_name,
            recommended_next_step=parsed.recommended_next_step,
            session_id=request.session_id,
            model=f"ollama:{settings.ollama_model}",
        )
        return _guard_non_business_escalation(request, response)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ollama failed: %s", exc)
        return _fallback_response(request, reason=f"ollama: {exc}")
