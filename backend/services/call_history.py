"""Persist and query call history for Ivan's control panel (ТЗ must-have)."""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import CallLog
from backend.schemas import CallHistoryItem, CallRequest, CallResponse, CallStats

logger = logging.getLogger(__name__)


def save_call_log(db: Session, request: CallRequest, response: CallResponse) -> CallLog:
    row = CallLog(
        session_id=request.session_id,
        caller_phone=request.client_phone or "unknown",
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
    logger.info("CallLog saved id=%s critical=%s intent=%s", row.id, row.is_critical, row.intent)
    return row


def list_call_logs(db: Session, *, critical_only: bool = False, limit: int = 100) -> list[CallLog]:
    stmt = select(CallLog).order_by(CallLog.created_at.desc()).limit(limit)
    if critical_only:
        stmt = stmt.where(CallLog.is_critical.is_(True))
    return list(db.scalars(stmt).all())


def get_call_log(db: Session, call_id: int) -> CallLog | None:
    return db.get(CallLog, call_id)


def summarize_call_logs(db: Session, *, limit: int = 500) -> CallStats:
    rows = list_call_logs(db, critical_only=False, limit=limit)
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


def call_log_to_item(row: CallLog) -> CallHistoryItem:
    return CallHistoryItem(
        id=row.id,
        session_id=row.session_id,
        caller_phone=row.caller_phone,
        user_message=row.user_message,
        agent_response=row.agent_response,
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
