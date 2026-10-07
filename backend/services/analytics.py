"""Простая аналитика по истории звонков (ТЗ: усиление ценности)."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import CallLog
from backend.services.telegram_notify import normalize_phone


def build_call_stats(
    db: Session,
    *,
    line_phone: str | None = None,
    limit: int = 500,
) -> dict:
    stmt = select(CallLog).order_by(CallLog.created_at.desc()).limit(limit)
    phone = normalize_phone(line_phone or "")
    if phone:
        stmt = stmt.where(CallLog.line_phone == phone)
    rows = list(db.scalars(stmt).all())
    total = len(rows)
    critical = sum(1 for r in rows if r.is_critical)
    by_intent = Counter(r.intent or "other" for r in rows)
    by_action = Counter(r.action_required or "continue_dialog" for r in rows)
    note = (
        f"Аналитика по линии {phone}."
        if phone
        else "Аналитика по локальной SQLite-истории (прототип для Ивана)."
    )
    return {
        "total_calls": total,
        "critical_calls": critical,
        "critical_share": round(critical / total, 3) if total else 0.0,
        "by_intent": dict(by_intent.most_common()),
        "by_action": dict(by_action.most_common()),
        "sample_limit": limit,
        "line_phone": phone or None,
        "note": note,
    }
