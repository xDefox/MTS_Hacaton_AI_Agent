"""Telegram-бот Ивана: дашборд, история, настройки + эмуляция звонка."""

import asyncio
import logging
import os
import time
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommand, CallbackQuery
from dotenv import load_dotenv

from backend.services.service_settings import get_settings as get_line_settings
from backend.services.telegram_notify import (
    activate_line,
    format_phone,
    last_pending_phone,
    normalize_phone,
    phone_for_chat,
)
from frontend.tg_call_demo import (
    active_call,
    end_call_session,
    is_in_call,
    process_text_turn,
    process_voice_turn,
    reply_with_agent_audio,
    start_call_session,
    synthesize_and_send_voice,
)
from frontend.tg_dashboard import (
    BTN_ALL,
    BTN_CALL,
    BTN_CRIT,
    BTN_DASH,
    BTN_HANGUP,
    BTN_SET,
    call_keyboard,
    format_detail,
    format_history,
    format_settings,
    format_stats,
    history_keyboard,
    main_keyboard,
    settings_keyboard,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TOKEN = (os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
if not TOKEN:
    raise SystemExit("Нет TG_BOT_TOKEN: положите токен в .env в корне репозитория")

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

bot = Bot(token=TOKEN)
dp = Dispatcher()
_last_start: dict[int, float] = {}


def _line_phone(chat_id: int, start_args: str = "") -> str:
    return (
        normalize_phone(start_args)
        or phone_for_chat(chat_id)
        or last_pending_phone()
    )


def _display_phone(chat_id: int) -> str:
    return format_phone(phone_for_chat(chat_id) or last_pending_phone())


async def _activate_via_api(phone: str, chat_id: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{API_BASE}/api/v1/telegram/subscribe",
                json={"phone": phone, "chat_id": chat_id},
            )
        if resp.status_code == 200:
            return
    except httpx.RequestError:
        logging.warning("API недоступен, пишем линию локально")
    activate_line(phone, chat_id)


async def _api_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await client.get(f"{API_BASE}{path}", params=params)


async def _line_settings_for(chat_id: int) -> dict:
    phone = phone_for_chat(chat_id) or last_pending_phone()
    if not phone:
        return get_line_settings("")
    try:
        resp = await _api_get("/api/v1/service/settings", {"phone": phone})
        if resp.status_code == 200:
            return resp.json()
    except httpx.RequestError:
        pass
    return get_line_settings(phone)


async def _guard_busy(message: types.Message) -> bool:
    """True = сейчас идёт звонок, команду отклонили."""
    if not is_in_call(message.chat.id):
        return False
    await message.answer(
        "Идёт эмуляция звонка. Отправьте голосовое или нажмите «Завершить звонок».",
        reply_markup=call_keyboard(),
    )
    return True


async def _send_history(message: types.Message, *, critical: bool) -> None:
    if await _guard_busy(message):
        return
    prefs = await _line_settings_for(message.chat.id)
    if not prefs.get("history", True):
        await message.answer(
            "История выключена в приложении МТС.\n"
            "Включите «История звонков и саммари» в настройках услуги.",
            reply_markup=main_keyboard(),
        )
        return
    phone = phone_for_chat(message.chat.id) or last_pending_phone()
    if not phone:
        await message.answer(
            "Нет номера линии. Откройте приложение МТС или /start с номером.",
            reply_markup=main_keyboard(),
        )
        return
    try:
        resp = await _api_get(
            "/api/v1/calls",
            {"phone": phone, "limit": 12, "critical_only": critical},
        )
    except httpx.RequestError:
        await message.answer(
            "Не удалось связаться с API. Запустите uvicorn на :8000.",
            reply_markup=main_keyboard(),
        )
        return
    if resp.status_code != 200:
        await message.answer("История недоступна: бэкенд не ответил.")
        return
    payload = resp.json()
    items = payload.get("items") or []
    total = int(payload.get("total") or len(items))
    await message.answer(
        format_history(items, critical=critical, total=total),
        parse_mode="HTML",
        reply_markup=history_keyboard(items, critical=critical),
    )


async def _send_stats(message: types.Message) -> None:
    if await _guard_busy(message):
        return
    phone = phone_for_chat(message.chat.id) or last_pending_phone()
    if not phone:
        await message.answer(
            "Нет номера линии. Откройте приложение МТС или /start с номером.",
            reply_markup=main_keyboard(),
        )
        return
    try:
        resp = await _api_get("/api/v1/calls/stats", {"phone": phone})
    except httpx.RequestError:
        await message.answer(
            "Не удалось связаться с API. Запустите uvicorn на :8000.",
            reply_markup=main_keyboard(),
        )
        return
    if resp.status_code != 200:
        await message.answer("Дашборд недоступен: бэкенд не ответил.")
        return
    await message.answer(
        format_stats(resp.json()),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


async def _send_settings(message: types.Message) -> None:
    if await _guard_busy(message):
        return
    prefs = await _line_settings_for(message.chat.id)
    await message.answer(
        format_settings(_display_phone(message.chat.id), prefs),
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


async def _send_detail(message: types.Message, call_id: int) -> None:
    phone = phone_for_chat(message.chat.id) or last_pending_phone()
    if not phone:
        await message.answer("Нет номера линии для просмотра карточки.")
        return
    try:
        resp = await _api_get(f"/api/v1/calls/{call_id}", {"phone": phone})
    except httpx.RequestError:
        await message.answer("Не удалось связаться с API.")
        return
    if resp.status_code != 200:
        await message.answer(f"Карточка #{call_id} не найдена на вашей линии.")
        return
    await message.answer(format_detail(resp.json()), parse_mode="HTML")


async def _begin_demo_call(message: types.Message) -> None:
    chat_id = message.chat.id
    if is_in_call(chat_id):
        await message.answer(
            "Звонок уже идёт. Говорите голосом или завершите его.",
            reply_markup=call_keyboard(),
        )
        return

    phone = phone_for_chat(chat_id) or last_pending_phone()
    prefs = await _line_settings_for(chat_id)
    session = start_call_session(chat_id=chat_id, line_phone=phone or "", prefs=prefs)
    greeting = session["greeting"]
    tpl_note = (
        "Приветствие из шаблона линии."
        if prefs.get("scenarios") and (prefs.get("template_greeting") or "").strip()
        else "Шаблон выключен — стандартное приветствие."
    )

    await message.answer(
        f"📞 <b>Входящий звонок (демо)</b>\n"
        f"Линия: {format_phone(phone) if phone else '—'}\n"
        f"Сессия: <code>{session['session_id']}</code>\n"
        f"{tpl_note}\n\n"
        "Агент на линии. Отправьте <b>голосовое</b> сообщение (можно и текст).\n"
        "Ответ придёт голосом и попадёт в историю.",
        parse_mode="HTML",
        reply_markup=call_keyboard(),
    )
    await message.answer(f"🗣 Агент: {greeting}")
    ok = await synthesize_and_send_voice(
        message,
        api_base=API_BASE,
        text=greeting,
        caption="Приветствие агента",
    )
    if not ok:
        await message.answer(
            "Не удалось озвучить приветствие (проверьте uvicorn / TTS). "
            "Текст выше — можно продолжать голосом."
        )


async def _hangup_demo_call(message: types.Message) -> None:
    session = end_call_session(message.chat.id)
    if not session:
        await message.answer("Активного звонка нет.", reply_markup=main_keyboard())
        return
    turns = int(session.get("turns") or 0)
    ids = session.get("call_ids") or []
    ids_txt = ", ".join(f"#{i}" for i in ids) if ids else "нет карточек"
    elapsed = int(time.time() - float(session.get("started_at") or time.time()))
    await message.answer(
        f"⏹ Звонок завершён ({elapsed} с).\n"
        f"Реплик: {turns}\n"
        f"В истории: {ids_txt}\n"
        "Смотрите «Все звонки» / дашборд.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    chat_id = message.chat.id
    now = time.monotonic()
    if now - _last_start.get(chat_id, 0) < 3:
        return
    _last_start[chat_id] = now

    phone = _line_phone(chat_id, command.args or "")
    if phone:
        await _activate_via_api(phone, chat_id)
    display = format_phone(phone) if phone else "—"
    await message.answer(
        f"Услуга активна на номере {display}\n"
        "Дашборд внизу. «Начать звонок» — демо голосового агента.\n"
        "Настройки услуги — в приложении МТС.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("menu"))
@dp.message(Command("dashboard"))
@dp.message(F.text == BTN_DASH)
async def cmd_dashboard(message: types.Message):
    await _send_stats(message)


@dp.message(Command("history"))
@dp.message(F.text == BTN_ALL)
async def cmd_history(message: types.Message):
    await _send_history(message, critical=False)


@dp.message(Command("important"))
@dp.message(F.text == BTN_CRIT)
async def cmd_important(message: types.Message):
    await _send_history(message, critical=True)


@dp.message(Command("settings"))
@dp.message(F.text == BTN_SET)
async def cmd_settings(message: types.Message):
    await _send_settings(message)


@dp.message(Command("demo_call"))
@dp.message(F.text == BTN_CALL)
async def cmd_demo_call(message: types.Message):
    await _begin_demo_call(message)


@dp.message(Command("hangup"))
@dp.message(F.text == BTN_HANGUP)
async def cmd_hangup(message: types.Message):
    await _hangup_demo_call(message)


@dp.message(Command("call"))
async def cmd_call(message: types.Message, command: CommandObject):
    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Карточка: /call 12\nДемо-звонок: «Начать звонок» или /demo_call")
        return
    if await _guard_busy(message):
        return
    await _send_detail(message, int(raw))


@dp.message(F.voice | F.audio)
async def on_voice_during_call(message: types.Message):
    session = active_call(message.chat.id)
    if session is None:
        await message.answer(
            "Чтобы говорить с агентом, нажмите «Начать звонок».",
            reply_markup=main_keyboard(),
        )
        return

    wait = await message.answer("⏳ Слушаю… распознаю и думаю (STT + LLM + TTS).")
    payload = await process_voice_turn(
        message,
        bot=bot,
        api_base=API_BASE,
        session=session,
    )
    try:
        await wait.delete()
    except Exception:
        pass

    if payload is None:
        await message.answer(
            "Не удалось обработать голос. Проверьте uvicorn и Ollama.",
            reply_markup=call_keyboard(),
        )
        return
    if payload.get("error"):
        await message.answer(
            f"Ошибка API ({payload.get('status_code')}): {payload['error'][:400]}",
            reply_markup=call_keyboard(),
        )
        return

    await reply_with_agent_audio(message, api_base=API_BASE, payload=payload)
    action = str(payload.get("action_required") or "")
    if action == "transfer_to_human":
        await message.answer(
            "⚠️ Агент предлагает перевод на человека (заглушка). "
            "Можете продолжить или завершить звонок.",
            reply_markup=call_keyboard(),
        )


@dp.message(F.text)
async def on_text_during_call(message: types.Message):
    """Текст во время звонка — fallback, если нет микрофона."""
    if not is_in_call(message.chat.id):
        return
    text = (message.text or "").strip()
    if not text or text in {BTN_CALL, BTN_HANGUP, BTN_DASH, BTN_ALL, BTN_CRIT, BTN_SET}:
        return
    session = active_call(message.chat.id)
    if session is None:
        return

    wait = await message.answer("⏳ Обрабатываю текст как реплику звонящего…")
    payload = await process_text_turn(
        message,
        api_base=API_BASE,
        session=session,
        text=text,
    )
    try:
        await wait.delete()
    except Exception:
        pass

    if payload is None:
        await message.answer("API недоступен.", reply_markup=call_keyboard())
        return
    if payload.get("error"):
        await message.answer(
            f"Ошибка API ({payload.get('status_code')}): {payload['error'][:400]}",
            reply_markup=call_keyboard(),
        )
        return
    await reply_with_agent_audio(message, api_base=API_BASE, payload=payload)


@dp.callback_query(F.data == "dash")
async def cb_dash(query: CallbackQuery):
    await query.answer()
    if query.message:
        await _send_stats(query.message)


@dp.callback_query(F.data == "hist:all")
async def cb_hist_all(query: CallbackQuery):
    await query.answer()
    if query.message:
        await _send_history(query.message, critical=False)


@dp.callback_query(F.data == "hist:crit")
async def cb_hist_crit(query: CallbackQuery):
    await query.answer()
    if query.message:
        await _send_history(query.message, critical=True)


@dp.callback_query(F.data.startswith("call:"))
async def cb_call(query: CallbackQuery):
    await query.answer()
    raw = (query.data or "").split(":", 1)[-1]
    if query.message and raw.isdigit():
        await _send_detail(query.message, int(raw))


async def main():
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Активировать услугу"),
            BotCommand(command="demo_call", description="Начать демо-звонок"),
            BotCommand(command="hangup", description="Завершить демо-звонок"),
            BotCommand(command="dashboard", description="Аналитика звонков"),
            BotCommand(command="history", description="Все звонки"),
            BotCommand(command="important", description="Только важные"),
            BotCommand(command="settings", description="Настройки из приложения"),
            BotCommand(command="call", description="Карточка: /call 12"),
        ]
    )
    me = await bot.get_me()
    logging.info(
        "Бот @%s: demo call / dashboard / history / important / settings",
        me.username,
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
