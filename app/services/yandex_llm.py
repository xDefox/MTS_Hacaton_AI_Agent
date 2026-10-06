"""YandexGPT client via Yandex AI Studio SDK."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.config import Settings, get_settings
from app.prompts.system_ivan import build_system_prompt
from app.schemas import (
    ActionRequired,
    AgentLLMOutput,
    CallRequest,
    CallResponse,
    Intent,
    Priority,
)

logger = logging.getLogger(__name__)


class YandexLLMError(RuntimeError):
    """Raised when the model call or JSON parsing fails after retries."""


def _build_messages(request: CallRequest, system_prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "text": system_prompt}]

    if request.dialog_history:
        for turn in request.dialog_history:
            role = turn.get("role", "user")
            text = turn.get("text", "")
            if role in {"user", "assistant", "system"} and text:
                messages.append({"role": role, "text": text})

    phone = request.client_phone or "unknown"
    user_block = (
        f"session_id: {request.session_id}\n"
        f"client_phone: {phone}\n"
        f"caller_message: {request.user_message}"
    )
    messages.append({"role": "user", "text": user_block})
    return messages


def _extract_text(result: Any) -> str:
    """Normalize SDK result shapes to a single text string."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    text = getattr(result, "text", None)
    if isinstance(text, str) and text:
        return text
    try:
        # GPTModelResult is often indexable: result[0].text
        first = result[0]
        first_text = getattr(first, "text", None)
        if isinstance(first_text, str):
            return first_text
    except (TypeError, IndexError, KeyError):
        pass
    return str(result)


def _parse_output(raw_text: str) -> AgentLLMOutput:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(cleaned)
    return AgentLLMOutput.model_validate(data)


def _run_yandex_sync(messages: list[dict[str, str]], settings: Settings) -> str:
    try:
        from yandex_ai_studio_sdk import AIStudio
    except ImportError as exc:
        raise YandexLLMError(
            "Package yandex-ai-studio-sdk is not installed. Run: pip install -r requirements.txt"
        ) from exc

    if not settings.yc_folder_id or not settings.yc_api_key:
        raise YandexLLMError(
            "YC_FOLDER_ID and YC_API_KEY must be set in .env (see .env.example)."
        )

    sdk = AIStudio(folder_id=settings.yc_folder_id, auth=settings.yc_api_key)
    model = sdk.models.completions(
        settings.yandex_model,
        model_version=settings.yandex_model_version,
    )
    model = model.configure(
        temperature=settings.yandex_temperature,
        response_format=AgentLLMOutput,
    )

    started = time.perf_counter()
    result = model.run(messages)
    latency_ms = int((time.perf_counter() - started) * 1000)
    text = _extract_text(result)
    logger.info("YandexGPT ok latency_ms=%s chars=%s", latency_ms, len(text))
    return text


def _fallback_response(request: CallRequest, reason: str) -> CallResponse:
    """Safe degraded answer so the demo API stays alive if the model fails."""
    logger.warning("Using fallback response: %s", reason)
    text_lower = request.user_message.lower()
    wants_human = any(
        phrase in text_lower
        for phrase in ("соедините", "менеджер", "с человеком", "с иваном", "оператор")
    )
    is_critical = wants_human or any(
        word in text_lower
        for word in ("срочно", "договор", "оплат", "жалоб", "мошен", "авария", "пилот")
    )

    if wants_human:
        agent_response = (
            "Понял вас. Соединяю с менеджером. "
            "Разговор может записываться для передачи информации владельцу."
        )
        action = ActionRequired.transfer_to_human
        intent = Intent.escalation
        summary = "Звонящий запросил соединение с человеком. Требуется срочная эскалация."
        next_step = "Принять звонок / перезвонить немедленно"
    elif is_critical:
        agent_response = (
            "Понимаю важность вопроса. Зафиксировал обращение и передам владельцу для быстрого перезвона. "
            "Разговор может записываться для передачи информации владельцу."
        )
        action = ActionRequired.callback_recommended
        intent = Intent.support_request
        summary = f"Важное обращение. Текст: {request.user_message[:240]}"
        next_step = "Перезвонить сегодня"
    else:
        agent_response = (
            "Здравствуйте! Я ИИ-помощник компании. Разговор может записываться "
            "для передачи информации владельцу. Расскажите, пожалуйста, по какому вопросу звоните?"
        )
        action = ActionRequired.continue_dialog
        intent = Intent.other
        summary = f"Обычное обращение. Текст: {request.user_message[:240]}"
        next_step = "Просмотреть резюме в Telegram"

    return CallResponse(
        agent_response=agent_response,
        is_critical=is_critical,
        priority=Priority.critical if wants_human else (Priority.high if is_critical else Priority.normal),
        intent=intent,
        action_required=action,
        summary=summary,
        caller_name=None,
        recommended_next_step=next_step,
        session_id=request.session_id,
        model="fallback",
    )


async def process_call_with_yandex(
    request: CallRequest,
    settings: Settings | None = None,
) -> CallResponse:
    settings = settings or get_settings()

    if not settings.yc_folder_id or not settings.yc_api_key:
        return _fallback_response(
            request,
            reason="YC_FOLDER_ID / YC_API_KEY not configured",
        )

    system_prompt = build_system_prompt(settings)
    messages = _build_messages(request, system_prompt)

    last_error: Exception | None = None
    attempts = 1 + max(0, settings.yandex_max_retries)

    for attempt in range(1, attempts + 1):
        try:
            if attempt > 1:
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "text": (
                            "Предыдущий ответ был невалидным JSON. "
                            "Верни строго один JSON-объект по схеме, без markdown."
                        ),
                    },
                ]

            raw = await asyncio.to_thread(_run_yandex_sync, messages, settings)
            parsed = _parse_output(raw)
            return CallResponse(
                agent_response=parsed.agent_response,
                is_critical=parsed.is_critical,
                priority=parsed.priority,
                intent=parsed.intent,
                action_required=parsed.action_required,
                summary=parsed.summary,
                caller_name=parsed.caller_name,
                recommended_next_step=parsed.recommended_next_step,
                session_id=request.session_id,
                model=f"{settings.yandex_model}:{settings.yandex_model_version}",
            )
        except Exception as exc:  # noqa: BLE001 — last attempt falls back
            last_error = exc
            logger.exception("YandexGPT attempt %s/%s failed: %s", attempt, attempts, exc)

    return _fallback_response(request, reason=str(last_error) if last_error else "unknown")
