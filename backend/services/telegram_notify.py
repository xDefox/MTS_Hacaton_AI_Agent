"""Уведомления Ивану в Telegram после реального process_call / process_call_voice."""

from __future__ import annotations

import html
import logging

import httpx

from backend.config import ROOT_DIR, get_settings

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


def list_subscribers() -> list[int]:
    ids: set[int] = set()
    extra = (get_settings().tg_chat_id or "").strip()
    if extra:
        for part in extra.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
                ids.add(int(part))
    if SUBSCRIBERS_PATH.exists():
        for line in SUBSCRIBERS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.isdigit() or (line.startswith("-") and line[1:].isdigit()):
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
    who = html.escape(caller_name or "")
    who = f" ({who})" if who else ""
    title = "⚠️ ВАЖНЫЙ ЗВОНОК" if is_critical else "ℹ️ Входящий вызов"
    parts = [
        "📋 <b>Отчёт нейросети</b>",
        f"{title}{who}",
        "",
        f"📱 Номер: <code>{html.escape(phone or 'unknown')}</code>",
        f"🏷 Intent: <code>{html.escape(str(intent))}</code> · "
        f"приоритет: <code>{html.escape(str(priority))}</code>",
    ]
    if transcript:
        parts += ["", "<b>Расшифровка</b>", html.escape(transcript)]
    parts += [
        "",
        "<b>Резюме</b>",
        html.escape(summary or "—"),
        "",
        "<b>Что ответил агент</b>",
        html.escape(agent_response or "—"),
        "",
        "<b>Что сделать</b>",
        html.escape(recommended_next_step or "—"),
    ]
    return "\n".join(parts)


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
    token = (get_settings().tg_bot_token or "").strip()
    chats = list_subscribers()
    if not token or not chats:
        logger.info("Telegram skip: token=%s subscribers=%s", bool(token), chats)
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
            try:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Telegram %s: %s", chat_id, resp.text[:300])
            except httpx.RequestError:
                logger.exception("Telegram send failed chat_id=%s", chat_id)


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
