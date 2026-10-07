"""Эмуляция входящего звонка в Telegram: голос → API → голос + история."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile, Message

from frontend.tg_dashboard import demo_greeting_text, format_call_turn

logger = logging.getLogger(__name__)

# chat_id → активная сессия звонка
_active_calls: dict[int, dict[str, Any]] = {}

VOICE_TIMEOUT = 180.0
DEFAULT_CALLER = "79000000000"


def active_call(chat_id: int) -> dict[str, Any] | None:
    return _active_calls.get(chat_id)


def is_in_call(chat_id: int) -> bool:
    return chat_id in _active_calls


def start_call_session(*, chat_id: int, line_phone: str, prefs: dict) -> dict[str, Any]:
    greeting = demo_greeting_text(prefs)
    faq = ""
    if prefs.get("scenarios"):
        faq = (prefs.get("template_faq") or "").strip()
    session = {
        "session_id": f"tg-demo-{chat_id}-{int(time.time())}",
        "line_phone": line_phone or "unknown",
        "caller_phone": DEFAULT_CALLER,
        "greeting": greeting,
        "faq": faq,
        "started_at": time.time(),
        "turns": 0,
        "call_ids": [],
        # Disclosure уже в приветствии — бэкенд не должен повторять
        "dialog_history": [{"role": "assistant", "text": greeting}],
        "disclosed": True,
    }
    if faq:
        session["dialog_history"].append(
            {
                "role": "assistant",
                "text": f"Справка по FAQ линии:\n{faq[:800]}",
            }
        )
    _active_calls[chat_id] = session
    return session


def end_call_session(chat_id: int) -> dict[str, Any] | None:
    return _active_calls.pop(chat_id, None)


async def synthesize_and_send_voice(
    message: Message,
    *,
    api_base: str,
    text: str,
    caption: str | None = None,
) -> bool:
    """TTS через API и отправка голосового/аудио в чат. True если аудио ушло."""
    spoken = (text or "").strip()
    if not spoken:
        return False
    try:
        async with httpx.AsyncClient(timeout=VOICE_TIMEOUT) as client:
            resp = await client.post(
                f"{api_base}/api/v1/synthesize",
                json={"text": spoken[:2000]},
            )
            if resp.status_code != 200:
                logger.warning("synthesize failed: %s %s", resp.status_code, resp.text[:200])
                return False
            payload = resp.json()
            audio_url = payload.get("audio_url")
            if not audio_url:
                return False
            url = audio_url if str(audio_url).startswith("http") else f"{api_base}{audio_url}"
            audio_resp = await client.get(url)
            if audio_resp.status_code != 200:
                return False
            data = audio_resp.content
            filename = str(payload.get("filename") or "reply.wav")
    except httpx.RequestError:
        logger.exception("synthesize/download failed")
        return False

    file = BufferedInputFile(data, filename=filename)
    try:
        if filename.lower().endswith(".ogg"):
            await message.answer_voice(file, caption=caption)
        else:
            await message.answer_audio(file, caption=caption, title="Ответ агента")
        return True
    except Exception:
        logger.exception("send audio failed")
        try:
            await message.answer_document(file, caption=caption)
            return True
        except Exception:
            logger.exception("send document audio failed")
            return False


async def process_voice_turn(
    message: Message,
    *,
    bot: Bot,
    api_base: str,
    session: dict[str, Any],
) -> dict[str, Any] | None:
    """Скачать ГС из Telegram → process_call_voice(with_audio) → ответ."""
    voice = message.voice or message.audio
    if voice is None:
        return None
    try:
        raw = await bot.download(voice)
    except Exception:
        logger.exception("telegram download voice failed")
        return None
    if raw is None:
        return None
    audio_bytes = raw.read() if hasattr(raw, "read") else bytes(raw)

    filename = "caller.ogg"
    content_type = "audio/ogg"
    if message.audio and (message.audio.file_name or "").lower().endswith(".wav"):
        filename = "caller.wav"
        content_type = "audio/wav"

    history_json = json.dumps(session.get("dialog_history") or [], ensure_ascii=False)
    data = {
        "session_id": session["session_id"],
        "line_phone": session.get("line_phone") or "",
        "client_phone": session.get("caller_phone") or DEFAULT_CALLER,
        "direction": "inbound",
        "lang": "ru-RU",
        "audio_format": "oggopus" if filename.endswith(".ogg") else "lpcm",
        "with_audio": "true",
        "dialog_history_json": history_json,
    }
    files = {"audio": (filename, audio_bytes, content_type)}

    try:
        async with httpx.AsyncClient(timeout=VOICE_TIMEOUT) as client:
            resp = await client.post(
                f"{api_base}/api/v1/process_call_voice",
                data=data,
                files=files,
            )
    except httpx.RequestError:
        logger.exception("process_call_voice request failed")
        return None

    if resp.status_code != 200:
        logger.warning("process_call_voice %s: %s", resp.status_code, resp.text[:300])
        return {"error": resp.text[:300], "status_code": resp.status_code}

    payload = resp.json()
    transcript = str(payload.get("transcript") or "").strip()
    agent = str(payload.get("agent_response") or "").strip()
    session["turns"] = int(session.get("turns") or 0) + 1
    if payload.get("call_id") is not None:
        session.setdefault("call_ids", []).append(payload["call_id"])
    hist = list(session.get("dialog_history") or [])
    if transcript:
        hist.append({"role": "user", "text": transcript})
    if agent:
        hist.append({"role": "assistant", "text": agent})
    session["dialog_history"] = hist[-12:]
    return payload


async def process_text_turn(
    message: Message,
    *,
    api_base: str,
    session: dict[str, Any],
    text: str,
) -> dict[str, Any] | None:
    """Текстовая реплика (fallback, если нет микрофона) → process_call + TTS."""
    body = {
        "session_id": session["session_id"],
        "user_message": text.strip(),
        "line_phone": session.get("line_phone") or "",
        "client_phone": session.get("caller_phone") or DEFAULT_CALLER,
        "direction": "inbound",
        "dialog_history": session.get("dialog_history") or [],
    }
    try:
        async with httpx.AsyncClient(timeout=VOICE_TIMEOUT) as client:
            resp = await client.post(
                f"{api_base}/api/v1/process_call",
                params={"with_audio": "true"},
                json=body,
            )
    except httpx.RequestError:
        logger.exception("process_call request failed")
        return None
    if resp.status_code != 200:
        return {"error": resp.text[:300], "status_code": resp.status_code}
    payload = resp.json()
    payload["transcript"] = text.strip()
    session["turns"] = int(session.get("turns") or 0) + 1
    if payload.get("call_id") is not None:
        session.setdefault("call_ids", []).append(payload["call_id"])
    hist = list(session.get("dialog_history") or [])
    hist.append({"role": "user", "text": text.strip()})
    hist.append({"role": "assistant", "text": str(payload.get("agent_response") or "")})
    session["dialog_history"] = hist[-12:]
    return payload


async def reply_with_agent_audio(
    message: Message,
    *,
    api_base: str,
    payload: dict[str, Any],
) -> None:
    """Текст карточки + голосовой ответ агента."""
    await message.answer(format_call_turn(payload), parse_mode="HTML")
    audio_url = payload.get("audio_url")
    agent = str(payload.get("agent_response") or "")
    sent = False
    if audio_url:
        try:
            url = audio_url if str(audio_url).startswith("http") else f"{api_base}{audio_url}"
            async with httpx.AsyncClient(timeout=60.0) as client:
                audio_resp = await client.get(url)
            if audio_resp.status_code == 200:
                name = str(audio_url).rsplit("/", 1)[-1] or "agent.wav"
                file = BufferedInputFile(audio_resp.content, filename=name)
                if name.lower().endswith(".ogg"):
                    await message.answer_voice(file)
                else:
                    await message.answer_audio(file, title="Ответ агента")
                sent = True
        except Exception:
            logger.exception("download agent audio failed")
    if not sent and agent:
        await synthesize_and_send_voice(message, api_base=api_base, text=agent)
