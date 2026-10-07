"""Persist and query call history for Ivan's control panel (ТЗ must-have)."""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import CallLog
from backend.schemas import CallHistoryItem, CallRequest, CallResponse, CallStats
from backend.services.telegram_notify import normalize_phone

logger = logging.getLogger(__name__)


def save_call_log(db: Session, request: CallRequest, response: CallResponse) -> CallLog:
    line = normalize_phone(request.line_phone or "")
    caller = normalize_phone(request.client_phone or "") or (request.client_phone or "unknown")
    direction = (request.direction or "inbound").strip().lower()
    if direction not in {"inbound", "outbound"}:
        direction = "inbound"
    row = CallLog(
        session_id=request.session_id,
        line_phone=line,
        caller_phone=caller,
        direction=direction,
        user_message=request.user_message,
        agent_response=response.agent_response,
        summary=response.summary,
        is_critical=response.is_critical,
        priority=response.priority.value if hasattr(response.priority, "value") else str(response.priority),
        intent=response.intent.value if hasattr(response.intent, "value") else str(response.intent),
        action_required=(
            response.action_required.value
            if hasattr(response.action_required, "value")
            else str(response.action_required)
        ),
        caller_name=response.caller_name,
        recommended_next_step=response.recommended_next_step,
        model=response.model,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "CallLog saved id=%s line=%s caller=%s critical=%s intent=%s",
        row.id,
        row.line_phone,
        row.caller_phone,
        row.is_critical,
        row.intent,
    )
    return row


def list_call_logs(
    db: Session,
    *,
    line_phone: str | None = None,
    critical_only: bool = False,
    session_id: str | None = None,
    limit: int = 100,
) -> list[CallLog]:
    stmt = select(CallLog).order_by(CallLog.created_at.desc()).limit(limit)
    phone = normalize_phone(line_phone or "")
    if phone:
        stmt = stmt.where(CallLog.line_phone == phone)
    if critical_only:
        stmt = stmt.where(CallLog.is_critical.is_(True))
    if session_id:
        stmt = stmt.where(CallLog.session_id == session_id)
    return list(db.scalars(stmt).all())


def get_call_log(db: Session, call_id: int) -> CallLog | None:
    return db.get(CallLog, call_id)


def get_call_log_for_line(db: Session, call_id: int, line_phone: str) -> CallLog | None:
    """Карточка только если принадлежит линии пользователя."""
    row = get_call_log(db, call_id)
    if row is None:
        return None
    phone = normalize_phone(line_phone or "")
    if not phone or normalize_phone(row.line_phone or "") != phone:
        return None
    return row


def summarize_call_logs(
    db: Session,
    *,
    line_phone: str | None = None,
    limit: int = 500,
) -> CallStats:
    rows = list_call_logs(db, line_phone=line_phone, critical_only=False, limit=limit)
    total = len(rows)
    critical = sum(1 for row in rows if row.is_critical)
    intents = Counter(row.intent or "other" for row in rows)
    actions = Counter(row.action_required or "continue_dialog" for row in rows)
    priorities = Counter(row.priority or "normal" for row in rows)
    share = round(100.0 * critical / total, 1) if total else 0.0
    return CallStats(
        total=total,
        critical=critical,
        routine=total - critical,
        critical_share=share,
        by_intent=dict(intents.most_common()),
        by_action=dict(actions.most_common()),
        by_priority=dict(priorities.most_common()),
    )


def update_call_log(db: Session, call_id: int, patch: dict) -> CallLog | None:
    """Ручная корректировка карточки звонка (CJM этап 4)."""
    row = get_call_log(db, call_id)
    if row is None:
        return None
    # input/output → колонки БД
    if "input" in patch and patch["input"] is not None:
        patch = {**patch, "user_message": patch["input"]}
    if "output" in patch and patch["output"] is not None:
        patch = {**patch, "agent_response": patch["output"]}
    allowed = {
        "user_message",
        "agent_response",
        "summary",
        "is_critical",
        "priority",
        "intent",
        "action_required",
        "caller_name",
        "recommended_next_step",
    }
    changed = False
    for key, value in patch.items():
        if key not in allowed or value is None:
            continue
        setattr(row, key, value)
        changed = True
    if changed:
        db.commit()
        db.refresh(row)
        logger.info("CallLog corrected id=%s fields=%s", call_id, list(patch.keys()))
    return row


def call_log_to_item(row: CallLog) -> CallHistoryItem:
    inbound = row.user_message or ""
    outbound = row.agent_response or ""
    return CallHistoryItem(
        id=row.id,
        session_id=row.session_id,
        line_phone=row.line_phone or "",
        caller_phone=row.caller_phone,
        direction=row.direction or "inbound",
        input=inbound,
        output=outbound,
        user_message=inbound,
        agent_response=outbound,
        summary=row.summary,
        is_critical=row.is_critical,
        priority=row.priority,
        intent=row.intent,
        action_required=row.action_required,
        caller_name=row.caller_name,
        recommended_next_step=row.recommended_next_step,
        model=row.model,
        created_at=row.created_at,
    )
