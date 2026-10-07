"""ORM models for Track 1 call history (ТЗ: контроль и управление)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CallLog(Base):
    """One processed caller turn / call card for Ivan's dashboard."""

    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    # Номер линии МТС (владелец услуги) — по нему фильтруем «свои» звонки
    line_phone: Mapped[str] = mapped_column(String(64), default="", index=True)
    # Номер звонящего (вторая сторона)
    caller_phone: Mapped[str] = mapped_column(String(64), default="unknown")
    # inbound = входящий на линию, outbound = исходящий
    direction: Mapped[str] = mapped_column(String(16), default="inbound")

    # вход (речь звонящего) / выход (ответ агента)
    user_message: Mapped[str] = mapped_column(Text)
    agent_response: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)

    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    priority: Mapped[str] = mapped_column(String(32), default="normal")
    intent: Mapped[str] = mapped_column(String(64), default="other")
    action_required: Mapped[str] = mapped_column(String(64), default="continue_dialog")

    caller_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recommended_next_step: Mapped[str] = mapped_column(String(256), default="")
    model: Mapped[str] = mapped_column(String(64), default="yandexgpt")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, index=True
    )
