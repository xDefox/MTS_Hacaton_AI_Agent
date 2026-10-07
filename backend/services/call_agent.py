"""Call agent: только внешний YandexGPT + routing rules (без Ollama)."""

from __future__ import annotations

import logging

from backend.config import Settings, get_settings
from backend.schemas import ActionRequired, CallRequest, CallResponse, Intent, Priority
from backend.services.routing_rules import match_rule
from backend.services.yandex_llm import (
    _guard_non_business_escalation,
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
    if rule.is_critical is False:
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
    return response.model_copy(
        update={"agent_response": ensure_ai_disclosure(response.agent_response)}
    )
