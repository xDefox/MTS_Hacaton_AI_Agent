"""Уведомления Ивану (CJM: Telegram о важных звонках).

По умолчанию пишет в data/notifications.jsonl (демо без бота).
Если заданы TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID — шлёт в Telegram.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.config import Settings, get_settings
from backend.schemas import CallResponse

logger = logging.getLogger(__name__)


def _notifications_path(settings: Settings):
    from backend.config import ROOT_DIR

    path = ROOT_DIR / "data" / "notifications.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _should_notify(response: CallResponse) -> bool:
    if response.is_critical:
        return True
    action = (
        response.action_required.value
        if hasattr(response.action_required, "value")
        else str(response.action_required)
    )
    return action in {"transfer_to_human", "callback_recommended", "offer_telegram_chat"}


def _payload(response: CallResponse, caller_phone: str | None) -> dict[str, Any]:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": response.session_id,
        "call_id": response.call_id,
        "caller_phone": caller_phone or "unknown",
        "is_critical": response.is_critical,
        "priority": str(response.priority),
        "intent": str(response.intent),
        "action_required": str(response.action_required),
        "summary": response.summary,
        "recommended_next_step": response.recommended_next_step,
        "caller_name": response.caller_name or "",
    }


def append_local_notification(payload: dict[str, Any], settings: Settings) -> str:
    path = _notifications_path(settings)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return str(path)


async def send_telegram_message(text: str, settings: Settings) -> bool:
    token = (settings.telegram_bot_token or "").strip()
    chat_id = (settings.telegram_chat_id or "").strip()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={"chat_id": chat_id, "text": text[:4000]})
    if resp.status_code >= 400:
        logger.warning("Telegram notify failed: %s %s", resp.status_code, resp.text[:200])
        return False
    return True


async def notify_ivan_if_needed(
    response: CallResponse,
    *,
    caller_phone: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if not _should_notify(response):
        return {"notified": False, "reason": "not_critical"}

    payload = _payload(response, caller_phone)
    path = append_local_notification(payload, settings)
    text = (
        f"🔔 Звонок для {settings.owner_name}\n"
        f"Важность: {'КРИТИЧНО' if response.is_critical else 'норма'}\n"
        f"Intent: {response.intent}\n"
        f"Action: {response.action_required}\n"
        f"Тел: {caller_phone or 'unknown'}\n"
        f"\n{response.summary}\n"
        f"\nДальше: {response.recommended_next_step}"
    )
    tg_ok = await send_telegram_message(text, settings)
    logger.info("Notify Ivan local=%s telegram=%s session=%s", path, tg_ok, response.session_id)
    return {
        "notified": True,
        "local_file": path,
        "telegram_sent": tg_ok,
        "payload": payload,
    }
