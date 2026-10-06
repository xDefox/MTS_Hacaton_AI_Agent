"""Уведомления Ивану в Telegram после process_call / process_call_voice."""

from __future__ import annotations

import html
import logging
import os

import httpx
from dotenv import load_dotenv

from backend.config import ROOT_DIR, get_settings

load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

SUBSCRIBERS_PATH = ROOT_DIR / "data" / "tg_chats.txt"
TELEGRAM_API = "https://api.telegram.org"


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
    """Короткий шаблон отчёта для чата Ивана."""
    flag = "⚠️ Важно" if is_critical else "ℹ️ Звонок"
    who = html.escape(caller_name) if caller_name else ""
    head = f"{flag}" + (f" · {who}" if who else "")
    lines = [
        f"{head}",
        f"Номер: {html.escape(phone or 'unknown')}",
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
