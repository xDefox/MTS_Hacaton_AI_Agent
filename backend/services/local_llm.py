"""Local LLM via Ollama (no external cloud API)."""

from __future__ import annotations

import logging
import re

import httpx

from backend.config import Settings, get_settings
from backend.prompts.system_ivan import build_system_prompt
from backend.schemas import (
    ActionRequired,
    CallRequest,
    CallResponse,
    Intent,
    Priority,
)
from backend.services.routing_rules import RoutingRule, match_rule
from backend.services.yandex_llm import (
    _build_messages,
    _default_next_step,
    _fallback_response,
    _guard_non_business_escalation,
    _is_bad_text_field,
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


def _snippet(text: str, n: int = 180) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:n]


def _russian_summary(request: CallRequest, rule: RoutingRule | None = None) -> str:
    msg = _snippet(request.user_message)
    if rule is None:
        return f"Звонок: {msg}" if msg else "Суть звонка неясна — нужно уточнение."
    if rule.is_critical:
        return (
            f"Важное обращение по правилу «{rule.name}». "
            f"Текст звонящего: {msg or '—'}. Нужна реакция Ивана."
        )
    return (
        f"Низкий приоритет («{rule.name}»). "
        f"Текст: {msg or '—'}. Эскалация не требуется."
    )


def _voice_line_for_rule(rule: RoutingRule) -> str:
    action = rule.action_required or "continue_dialog"
    if action == "transfer_to_human":
        return (
            "Здравствуйте! Понял, сейчас организую соединение со специалистом. "
            "Останьтесь, пожалуйста, на линии."
        )
    if action == "callback_recommended":
        return (
            "Здравствуйте! Зафиксировал ваш запрос. "
            "Иван или менеджер перезвонит вам в ближайшее время. Уточните удобный контакт?"
        )
    if action == "offer_telegram_chat":
        return (
            "Здравствуйте! Вопрос объёмный — удобнее продолжить в рабочем чате, "
            "там разберём детали. Могу зафиксировать контакт для связи."
        )
    if rule.intent == "spam":
        return (
            "Здравствуйте! Спасибо за предложение. Сейчас мы не рассматриваем такие услуги. "
            "Хорошего дня!"
        )
    if rule.intent == "faq":
        return (
            "Здравствуйте! Кратко подскажу по типовому вопросу. "
            "Если нужна уточнённая информация — оставьте контакт, передадим Ивану."
        )
    if rule.intent == "wrong_number":
        return "Здравствуйте! Похоже, вы ошиблись номером. Всего доброго!"
    return (
        "Здравствуйте! Я помощник Ивана. Расскажите, пожалуйста, цель звонка "
        "и название компании — так смогу помочь точнее."
    )


def _response_from_rule(
    request: CallRequest,
    rule: RoutingRule,
    settings: Settings,
) -> CallResponse:
    """Быстрый путь без Ollama: правило уже однозначно закрывает кейс."""
    intent = Intent(rule.intent) if rule.intent else Intent.other
    action = (
        ActionRequired(rule.action_required)
        if rule.action_required
        else ActionRequired.continue_dialog
    )
    critical = bool(rule.is_critical)
    priority = Priority.critical if critical else Priority.low
    return CallResponse(
        agent_response=ensure_ai_disclosure(_voice_line_for_rule(rule)),
        is_critical=critical,
        priority=priority,
        intent=intent,
        action_required=action,
        summary=_russian_summary(request, rule),
        caller_name=None,
        recommended_next_step=_default_next_step(action.value, critical),
        session_id=request.session_id,
        model=f"rules:{rule.id}",
    )


def _polish_fields(
    request: CallRequest,
    *,
    summary: str,
    next_step: str,
    action: str,
    is_critical: bool,
) -> tuple[str, str]:
    if _is_bad_text_field(summary):
        summary = _russian_summary(request)
    if _is_bad_text_field(next_step):
        next_step = _default_next_step(action, is_critical)
    return summary, next_step


async def process_call_with_ollama(
    request: CallRequest,
    settings: Settings | None = None,
) -> CallResponse:
    settings = settings or get_settings()

    # Скорость: если правило сработало — не ждём 3b на CPU
    if settings.ollama_rules_fast_path:
        rule = match_rule(request.user_message)
        if rule is not None:
            logger.info(
                "Local fast-path rule=%s session=%s",
                rule.id,
                request.session_id,
            )
            return _guard_non_business_escalation(
                request, _response_from_rule(request, rule, settings)
            )

    system_prompt = build_system_prompt(settings, compact=True)
    system_prompt += (
        "\nОтветь одним JSON. Поля summary и recommended_next_step — "
        "короткие русские фразы про этот звонок."
    )
    if request.dialog_history and len(request.dialog_history) > 2:
        request = request.model_copy(
            update={"dialog_history": request.dialog_history[-2:]}
        )
    messages = _build_messages(request, system_prompt)
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": _ollama_messages(messages),
        "stream": False,
        "format": "json",
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "temperature": settings.ollama_temperature,
            "num_ctx": settings.ollama_num_ctx,
            "num_predict": settings.ollama_num_predict,
            **(
                {"num_thread": settings.ollama_num_thread}
                if settings.ollama_num_thread > 0
                else {}
            ),
        },
    }

    try:
        timeout = httpx.Timeout(
            connect=10.0,
            read=settings.ollama_timeout_sec,
            write=30.0,
            pool=10.0,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            raise LocalLLMError(f"Ollama HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        raw = (data.get("message") or {}).get("content") or ""
        parsed = _parse_output(_extract_json_text(raw))
        caller_name = parsed.caller_name.strip() or None
        action = (
            parsed.action_required.value
            if hasattr(parsed.action_required, "value")
            else str(parsed.action_required)
        )
        summary, next_step = _polish_fields(
            request,
            summary=(parsed.summary or "").strip(),
            next_step=(parsed.recommended_next_step or "").strip(),
            action=action,
            is_critical=parsed.is_critical,
        )
        response = CallResponse(
            agent_response=ensure_ai_disclosure(parsed.agent_response),
            is_critical=parsed.is_critical,
            priority=parsed.priority,
            intent=parsed.intent,
            action_required=parsed.action_required,
            summary=summary,
            caller_name=caller_name,
            recommended_next_step=next_step,
            session_id=request.session_id,
            model=f"ollama:{settings.ollama_model}",
        )
        return _guard_non_business_escalation(request, response)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ollama failed: %s", exc)
        return _fallback_response(request, reason=f"ollama: {exc}")
