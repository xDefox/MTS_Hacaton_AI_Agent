"""Уведомления Ивану (CJM: Telegram о важных звонках).

По умолчанию пишет в data/notifications.jsonl (демо без бота).
Если заданы TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID — шлёт в Telegram.
"""

from __future__ import annotations

import html
import json
import logging
import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import httpx
from dotenv import load_dotenv

from backend.config import ROOT_DIR, Settings, get_settings
from backend.schemas import CallResponse

load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

SUBSCRIBERS_PATH = ROOT_DIR / "data" / "tg_chats.txt"
LINES_PATH = ROOT_DIR / "data" / "tg_lines.json"
TELEGRAM_API = "https://api.telegram.org"
_lock = Lock()


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


def list_notifications(settings: Settings | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    """Последние уведомления Ивану (CJM лента)."""
    settings = settings or get_settings()
    path = _notifications_path(settings)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(rows[-limit:]))


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

# --- Line activation API (from main / frontend) ---

def normalize_phone(raw: str) -> str:
    digits = "".join(c for c in (raw or "") if c.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def format_phone(digits: str) -> str:
    digits = normalize_phone(digits)
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    if digits:
        return "+" + digits
    return "—"


def _load_lines() -> dict:
    if not LINES_PATH.exists():
        return {}
    try:
        data = json.loads(LINES_PATH.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_lines(data: dict) -> None:
    LINES_PATH.parent.mkdir(parents=True, exist_ok=True)
    LINES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register_line(phone: str) -> str:
    """Фронт: номер из заглушки МТС (ещё без /start)."""
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("empty phone")
    with _lock:
        data = _load_lines()
        row = data.get(phone) or {"chat_id": None}
        row["activated"] = False
        row["updated_at"] = time.time()
        data[phone] = row
        _save_lines(data)
    return phone


def activate_line(phone: str, chat_id: int) -> str:
    """Бот /start: услуга активна на этом номере."""
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("empty phone")
    chat_id = int(chat_id)
    with _lock:
        data = _load_lines()
        data[phone] = {
            "chat_id": chat_id,
            "activated": True,
            "updated_at": time.time(),
        }
        _save_lines(data)
    add_subscriber(chat_id)
    logger.info("Line activated phone=%s chat_id=%s", phone, chat_id)
    return phone


def deactivate_line(phone: str) -> str:
    """Фронт: выход из услуги — линия снова ждёт /start."""
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("empty phone")
    with _lock:
        data = _load_lines()
        row = data.get(phone) or {"chat_id": None}
        row["activated"] = False
        row["updated_at"] = time.time()
        data[phone] = row
        _save_lines(data)
    logger.info("Line deactivated phone=%s", phone)
    return phone


def line_status(phone: str) -> dict:
    phone = normalize_phone(phone)
    with _lock:
        row = _load_lines().get(phone) or {}
    return {
        "phone": phone,
        "display": format_phone(phone),
        "activated": bool(row.get("activated")),
        "chat_id": row.get("chat_id"),
    }


def phone_for_chat(chat_id: int) -> str:
    chat_id = int(chat_id)
    with _lock:
        for phone, row in _load_lines().items():
            if row.get("chat_id") == chat_id:
                return phone
    return ""


def last_pending_phone() -> str:
    with _lock:
        items = list(_load_lines().items())
    pending = [(phone, row) for phone, row in items if not row.get("activated")]
    pool = pending or items
    if not pool:
        return ""
    pool.sort(key=lambda item: float(item[1].get("updated_at") or 0))
    return pool[-1][0]


def add_subscriber(chat_id: int) -> None:
    chat_id = int(chat_id)
    known = set(list_subscribers())
    if chat_id in known:
        return
    SUBSCRIBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUBSCRIBERS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{chat_id}\n")
    logger.info("Telegram subscriber added: %s", chat_id)


def list_subscribers() -> list[int]:
    ids: set[int] = set()
    extra = (
        os.getenv("TG_CHAT_ID")
        or (get_settings().tg_chat_id or "")
    ).strip()
    if extra:
        for part in extra.replace(";", ",").split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                ids.add(int(part))
    if SUBSCRIBERS_PATH.exists():
        for line in SUBSCRIBERS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.lstrip("-").isdigit():
                ids.add(int(line))
    with _lock:
        for row in _load_lines().values():
            cid = row.get("chat_id")
            if cid is not None:
                ids.add(int(cid))
    return sorted(ids)


def format_call_report(
    *,
    phone: str,
    summary: str,
    agent_response: str,
    recommended_next_step: str,
    intent: str,
    priority: str,
    is_critical: bool,
    caller_name: str | None = None,
    transcript: str | None = None,
) -> str:
    flag = "⚠️ Важно" if is_critical else "ℹ️ Звонок"
    who = html.escape(caller_name) if caller_name else ""
    head = f"{flag}" + (f" · {who}" if who else "")
    lines = [
        f"{head}",
        f"Номер: {html.escape(format_phone(phone) if phone else 'unknown')}",
        "",
        html.escape(summary or "—"),
        "",
        f"Агент: {html.escape(agent_response or '—')}",
    ]
    if recommended_next_step:
        lines += ["", f"Дальше: {html.escape(recommended_next_step)}"]
    if transcript:
        lines += ["", f"Расшифровка: {html.escape(transcript)}"]
    return "\n".join(lines)


async def notify_call_report(
    *,
    phone: str,
    summary: str,
    agent_response: str,
    recommended_next_step: str,
    intent: str,
    priority: str,
    is_critical: bool,
    caller_name: str | None = None,
    transcript: str | None = None,
) -> None:
    token = (os.getenv("TG_BOT_TOKEN") or get_settings().tg_bot_token or "").strip()
    chats = list_subscribers()
    if not token:
        logger.warning("Telegram skip: нет TG_BOT_TOKEN")
        return
    if not chats:
        logger.warning("Telegram skip: нет подписчиков. Иван должен нажать /start")
        return

    text = format_call_report(
        phone=phone,
        summary=summary,
        agent_response=agent_response,
        recommended_next_step=recommended_next_step,
        intent=intent,
        priority=priority,
        is_critical=is_critical,
        caller_name=caller_name,
        transcript=transcript,
    )
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=20.0) as client:
        for chat_id in chats:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            if resp.status_code != 200:
                logger.warning("Telegram %s: %s", chat_id, resp.text[:400])
            else:
                logger.info("Telegram report sent to %s", chat_id)


def payload_from_response(response, *, phone: str, transcript: str | None = None) -> dict:
    return {
        "phone": phone or "unknown",
        "summary": response.summary,
        "agent_response": response.agent_response,
        "recommended_next_step": response.recommended_next_step,
        "intent": getattr(response.intent, "value", response.intent),
        "priority": getattr(response.priority, "value", response.priority),
        "is_critical": response.is_critical,
        "caller_name": response.caller_name,
        "transcript": transcript,
    }
