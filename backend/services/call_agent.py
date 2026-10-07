"""Call agent: только внешний YandexGPT + routing rules (без Ollama)."""

from __future__ import annotations

import logging

from backend.config import Settings, get_settings
from backend.schemas import ActionRequired, CallRequest, CallResponse, Intent, Priority
from backend.services.content_filter import censor
from backend.services.routing_rules import classify_human_request, match_rule
from backend.services.service_settings import get_settings as get_line_settings
from backend.services.yandex_llm import (
    _guard_non_business_escalation,
    _strip_leading_disclosures,
    ensure_ai_disclosure,
    process_call_with_yandex,
)

logger = logging.getLogger(__name__)


def _safe_intent(value: str | None) -> Intent | None:
    if not value:
        return None
    try:
        return Intent(value)
    except ValueError:
        return None


def _safe_action(value: str | None) -> ActionRequired | None:
    if not value:
        return None
    try:
        return ActionRequired(value)
    except ValueError:
        return None


def apply_routing_rules(request: CallRequest, response: CallResponse) -> CallResponse:
    """Жёсткие правила из data/routing_rules.json перекрывают LLM (ТЗ: контроль)."""
    rule = match_rule(request.user_message)
    if rule is None:
        return response

    updates: dict = {}
    if rule.is_critical is not None:
        updates["is_critical"] = rule.is_critical
        updates["priority"] = Priority.critical if rule.is_critical else Priority.low
    intent = _safe_intent(rule.intent)
    if intent is not None:
        updates["intent"] = intent
    action = _safe_action(rule.action_required)
    if action is not None:
        updates["action_required"] = action
    msg = (request.user_message or "")[:180]
    if rule.id == "rule-human-unclear":
        updates["priority"] = Priority.normal
        updates["recommended_next_step"] = "Уточнить цель звонка"
        updates["summary"] = f"Просит соединить, цель неясна. Текст: {msg or '—'}."
    elif rule.is_critical is False:
        updates["recommended_next_step"] = "Не эскалировать — низкий приоритет"
        updates["summary"] = (
            f"Низкий приоритет («{rule.name}»). Текст звонящего: {msg or '—'}."
        )
    elif rule.is_critical is True:
        updates["recommended_next_step"] = "Срочно: нужна реакция Ивана"
        updates["summary"] = (
            f"Важное обращение («{rule.name}»). Текст: {msg or '—'}. "
            f"Действие: {rule.action_required or 'уточнить'}."
        )

    if not updates:
        return response

    logger.info(
        "Routing rule applied id=%s name=%s session=%s",
        rule.id,
        rule.name,
        request.session_id,
    )
    return response.model_copy(update=updates)


_DISCLOSURE_MARKER = "искусственным интеллектом"
_TRANSFER_PHRASES = ("соедин", "переключ", "перевожу", "переведу", "передаю звонок")

_BAIT_REPLY = (
    "Иван занимается ИТ-проектами, с этим вопросом помочь не сможем. "
    "Если есть рабочий вопрос — расскажите, передам."
)
_UNCLEAR_REPLY = (
    "Подскажите, пожалуйста, по какому вопросу? "
    "Если это касается проектов компании — сразу передам Ивану."
)
_NO_HOTLINE_REPLY = (
    "Сейчас соединить не получится. Зафиксировал обращение — Иван перезвонит."
)
_CHAT_ROUTED_INTENTS = {Intent.commercial, Intent.support_request, Intent.partnership}


def _already_disclosed(request: CallRequest) -> bool:
    """Предупреждение об ИИ уже звучало в этой сессии (история или прошлые реплики в БД)."""
    for turn in request.dialog_history or []:
        if turn.get("role") == "assistant" and _DISCLOSURE_MARKER in (turn.get("text") or "").lower():
            return True
    if not request.session_id:
        return False
    try:
        from sqlalchemy import select

        from backend.database import SessionLocal
        from backend.models import CallLog

        with SessionLocal() as db:
            row = db.execute(
                select(CallLog.id).where(CallLog.session_id == request.session_id).limit(1)
            ).first()
        return row is not None
    except Exception as exc:  # noqa: BLE001 — БД недоступна: лучше лишний раз предупредить
        logger.warning("Disclosure check failed session=%s: %s", request.session_id, exc)
        return False


def _apply_line_preferences(request: CallRequest, response: CallResponse) -> CallResponse:
    """Настройки линии из приложения: горячая линия выключена / маршрут в чат."""
    if not request.line_phone:
        return response
    prefs = get_line_settings(request.line_phone)
    if not prefs.get("hotline", True) and response.action_required == ActionRequired.transfer_to_human:
        logger.info("Line %s: hotline off, transfer -> callback", prefs.get("phone"))
        return response.model_copy(
            update={
                "action_required": ActionRequired.callback_recommended,
                "agent_response": _NO_HOTLINE_REPLY,
                "recommended_next_step": "Перезвонить клиенту (горячая линия выключена)",
            }
        )
    if (
        prefs.get("routing") == "chat"
        and response.action_required == ActionRequired.continue_dialog
        and response.intent in _CHAT_ROUTED_INTENTS
    ):
        return response.model_copy(update={"action_required": ActionRequired.offer_telegram_chat})
    return response


def _fix_contradicting_reply(request: CallRequest, response: CallResponse) -> CallResponse:
    """Модель пообещала соединить, а решение — не переводить: переписываем реплику."""
    if response.action_required == ActionRequired.transfer_to_human:
        return response
    text = (response.agent_response or "").lower()
    if not any(p in text for p in _TRANSFER_PHRASES):
        return response
    kind = classify_human_request(request.user_message)
    if kind == "bait":
        reply = _BAIT_REPLY
    elif kind == "unclear":
        reply = _UNCLEAR_REPLY
    elif response.action_required == ActionRequired.callback_recommended:
        reply = "Зафиксировал обращение и передам Ивану — он перезвонит."
    else:
        return response
    logger.info("Reply contradicted action=%s, rewritten (kind=%s)", response.action_required, kind)
    return response.model_copy(update={"agent_response": reply})


def finalize_agent_reply(request: CallRequest, text: str) -> str:
    """Цензура + предупреждение об ИИ только в первой реплике сессии."""
    text = censor(text or "")
    if _already_disclosed(request):
        return _strip_leading_disclosures(text) or "Слушаю вас."
    return ensure_ai_disclosure(text)


async def process_incoming_call(
    request: CallRequest,
    settings: Settings | None = None,
) -> CallResponse:
    settings = settings or get_settings()
    # Жёстко: только внешний YandexGPT. Ollama/local не используем.
    logger.info("LLM provider=yandex (external only)")
    response = await process_call_with_yandex(request, settings)
    response = apply_routing_rules(request, response)
    response = _guard_non_business_escalation(request, response)
    response = _apply_line_preferences(request, response)
    response = _fix_contradicting_reply(request, response)
    return response.model_copy(
        update={"agent_response": finalize_agent_reply(request, response.agent_response)}
    )
