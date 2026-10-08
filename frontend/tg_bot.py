"""Telegram-бот Ивана: дашборд, история, настройки + эмуляция звонка."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# python frontend/tg_bot.py и python -m frontend.tg_bot — оба из корня репо
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import httpx
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from dotenv import load_dotenv

from backend.services.service_settings import get_settings as get_line_settings
from backend.services.telegram_notify import (
    activate_line,
    format_phone,
    normalize_phone,
    phone_for_bind_token,
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
    dashboard_keyboard,
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

_LOCKED_HINT = (
    "<b>МТС · Умный секретарь</b>\n\n"
    "Канал уведомлений и демо-звонков по вашей линии.\n\n"
    "Активация — только из приложения МТС:\n"
    "Услуга → Подключить → «Перейти в Telegram».\n\n"
    "Без персональной ссылки из приложения доступ закрыт."
)

_WELCOME_BOUND = (
    "<b>МТС · Умный секретарь</b>\n"
    "Линия: <b>{phone}</b>\n"
    "────────────\n"
    "Доступны дашборд, история и демо входящего звонка.\n"
    "Настройки линии — в приложении МТС."
)

_CONFIRM_BIND_NEW = (
    "<b>МТС · Умный секретарь</b>\n\n"
    "Подключить уведомления к линии\n"
    "<b>{phone}</b>?"
)

_CONFIRM_BIND_SAME = (
    "<b>МТС · Умный секретарь</b>\n\n"
    "Эта линия уже привязана к чату:\n"
    "<b>{phone}</b>\n\n"
    "Продолжить доступ или перепривязать заново?"
)

_CONFIRM_BIND_SWITCH = (
    "<b>МТС · Умный секретарь</b>\n\n"
    "Сейчас в этом чате линия <b>{current}</b>.\n"
    "Ссылка из приложения — на <b>{target}</b>.\n\n"
    "Перевязать чат на новую линию или оставить текущую?"
)


def _display_phone(chat_id: int) -> str:
    phone = phone_for_chat(chat_id)
    return format_phone(phone) if phone else "—"


def _bind_new_kb(token: str) -> InlineKeyboardMarkup:
    """Первичная привязка: только токен в callback (номер не доверяем)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подключить",
                    callback_data=f"bind:yes:{token}"[:64],
                ),
                InlineKeyboardButton(text="Отмена", callback_data="bind:no"),
            ]
        ]
    )


def _bind_same_kb(token: str) -> InlineKeyboardMarkup:
    """Уже на этой линии: продолжить или перепривязать."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Продолжить доступ", callback_data="bind:stay")],
            [
                InlineKeyboardButton(
                    text="🔄 Перепривязать",
                    callback_data=f"bind:yes:{token}"[:64],
                ),
                InlineKeyboardButton(text="Отмена", callback_data="bind:no"),
            ],
        ]
    )


def _bind_switch_kb(token: str) -> InlineKeyboardMarkup:
    """Другая линия в ссылке: перевязать или оставить текущую."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔀 Перевязать на новую",
                    callback_data=f"bind:yes:{token}"[:64],
                )
            ],
            [InlineKeyboardButton(text="✅ Оставить текущую", callback_data="bind:stay")],
            [InlineKeyboardButton(text="Отмена", callback_data="bind:no")],
        ]
    )


async def _activate_via_api(chat_id: int, bind_token: str) -> tuple[bool, str]:
    """Привязка только по ключу из приложения. Возвращает (ok, phone|error)."""
    token = (bind_token or "").strip()
    if not token:
        return False, ""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{API_BASE}/api/v1/telegram/subscribe",
                json={"chat_id": chat_id, "bind_token": token, "phone": ""},
            )
        if resp.status_code == 200:
            phone = str((resp.json() or {}).get("phone") or "")
            return True, phone
        logging.warning("subscribe failed: %s", resp.text[:300])
        return False, ""
    except httpx.RequestError:
        logging.warning("API недоступен, пробуем локальный токен")
        phone = phone_for_bind_token(token)
        if not phone:
            return False, ""
        activate_line(phone, chat_id)
        return True, phone


async def _api_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await client.get(f"{API_BASE}{path}", params=params)


async def _line_settings_for(chat_id: int) -> dict:
    phone = phone_for_chat(chat_id)
    if not phone:
        return get_line_settings("")
    try:
        resp = await _api_get("/api/v1/service/settings", {"phone": phone})
        if resp.status_code == 200:
            return resp.json()
    except httpx.RequestError:
        pass
    return get_line_settings(phone)


async def _require_bound_phone(message: types.Message) -> str:
    phone = phone_for_chat(message.chat.id)
    if phone:
        return phone
    await message.answer(_LOCKED_HINT, parse_mode="HTML", reply_markup=main_keyboard())
    return ""


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
    phone = await _require_bound_phone(message)
    if not phone:
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
    phone = await _require_bound_phone(message)
    if not phone:
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
        format_stats(resp.json(), phone=phone),
        parse_mode="HTML",
        reply_markup=dashboard_keyboard(),
    )
    await message.answer(
        "Выберите раздел ниже или в меню.",
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
    phone = await _require_bound_phone(message)
    if not phone:
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

    phone = await _require_bound_phone(message)
    if not phone:
        return
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
    # Сначала голос (caption = текст приветствия), текст — только если TTS недоступен
    ok = await synthesize_and_send_voice(
        message,
        api_base=API_BASE,
        text=greeting,
        caption=f"🗣 {greeting[:200]}",
    )
    if not ok:
        await message.answer(
            f"🗣 Агент: {greeting}\n\n"
            "Не удалось озвучить (uvicorn / TTS). Можно продолжать голосом или текстом."
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

    raw = (command.args or "").strip()
    bound = phone_for_chat(chat_id)

    # Единственный вход: deep link ?start=<bind_token> из приложения.
    if raw.startswith("b") and len(raw) >= 8:
        phone = phone_for_bind_token(raw)
        if not phone:
            await message.answer(
                "<b>МТС · Умный секретарь</b>\n\n"
                "Ссылка недействительна или уже использована.\n"
                "Откройте приложение МТС и нажмите «Перейти в Telegram» снова.",
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
            return
        # Уже на этой линии → продолжить или перепривязать.
        if bound and bound == phone:
            await message.answer(
                _CONFIRM_BIND_SAME.format(phone=format_phone(phone)),
                parse_mode="HTML",
                reply_markup=_bind_same_kb(raw),
            )
            return
        # Другая линия в этом чате → перевязать или оставить.
        if bound and bound != phone:
            await message.answer(
                _CONFIRM_BIND_SWITCH.format(
                    current=format_phone(bound),
                    target=format_phone(phone),
                ),
                parse_mode="HTML",
                reply_markup=_bind_switch_kb(raw),
            )
            return
        await message.answer(
            _CONFIRM_BIND_NEW.format(phone=format_phone(phone)),
            parse_mode="HTML",
            reply_markup=_bind_new_kb(raw),
        )
        return

    if bound:
        await message.answer(
            _WELCOME_BOUND.format(phone=_display_phone(chat_id)),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(_LOCKED_HINT, parse_mode="HTML", reply_markup=main_keyboard())


@dp.callback_query(F.data.startswith("bind:"))
async def on_bind_confirm(callback: CallbackQuery):
    data = callback.data or ""
    if data == "bind:no":
        await callback.answer("Отменено")
        await callback.message.answer(
            "<b>МТС · Умный секретарь</b>\n\n"
            "Привязка отменена. Вернитесь в приложение МТС, "
            "если нужно подключить канал уведомлений.",
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )
        return
    if data == "bind:stay":
        await callback.answer("Ок")
        phone = phone_for_chat(callback.message.chat.id)
        if phone:
            await callback.message.answer(
                _WELCOME_BOUND.format(phone=format_phone(phone)),
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
        else:
            await callback.message.answer(
                _LOCKED_HINT, parse_mode="HTML", reply_markup=main_keyboard()
            )
        return
    # bind:yes:<token> — первичная привязка или перевязка
    parts = data.split(":", 2)
    if len(parts) < 3 or parts[1] != "yes":
        await callback.answer("Некорректно")
        return
    token = parts[2].strip()
    if not token.startswith("b"):
        await callback.answer("Нет ключа")
        await callback.message.answer(
            _LOCKED_HINT, parse_mode="HTML", reply_markup=main_keyboard()
        )
        return
    ok, phone = await _activate_via_api(callback.message.chat.id, token)
    await callback.answer("Готово" if ok else "Ошибка")
    if ok and phone:
        await callback.message.answer(
            _WELCOME_BOUND.format(phone=format_phone(phone)),
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )
    else:
        await callback.message.answer(
            "<b>МТС · Умный секретарь</b>\n\n"
            "Не удалось активировать канал. "
            "Снова нажмите «Перейти в Telegram» в приложении МТС.",
            parse_mode="HTML",
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
            "Не удалось обработать голос. Проверьте uvicorn и .env (YC_* или локальный Whisper).",
            reply_markup=call_keyboard(),
        )
        return
    if payload.get("error"):
        err = str(payload["error"])
        hint = ""
        if "YC_FOLDER_ID" in err or "YC_API_KEY" in err:
            hint = (
                "\n\nВ .env нет Yandex-ключей. Добавьте YC_FOLDER_ID и YC_API_KEY "
                "или перезапустите uvicorn после правки (STT уйдёт в Whisper)."
            )
        await message.answer(
            f"Ошибка API ({payload.get('status_code')}): {err[:400]}{hint}",
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


@dp.callback_query(F.data == "set")
async def cb_settings(query: CallbackQuery):
    await query.answer()
    if query.message:
        await _send_settings(query.message)


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
    # Корпоративное описание в профиле бота (вместо «бот Ивана» в about).
    try:
        await bot.set_my_name(name="МТС Умный секретарь")
    except Exception:
        logging.warning("set_my_name недоступен — задайте имя в @BotFather")
    try:
        await bot.set_my_short_description(
            short_description="МТС · канал уведомлений и демо линии умного секретаря"
        )
        await bot.set_my_description(
            description=(
                "Официальный канал услуги «Умный секретарь» МТС.\n\n"
                "Активация только из приложения МТС: "
                "Подключить услугу → «Перейти в Telegram».\n"
                "Без персональной ссылки из приложения бот недоступен."
            )
        )
    except Exception:
        logging.warning("set_my_description failed")
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="МТС · статус линии"),
            BotCommand(command="demo_call", description="Демо входящего звонка"),
            BotCommand(command="hangup", description="Завершить демо-звонок"),
            BotCommand(command="dashboard", description="Дашборд линии"),
            BotCommand(command="history", description="История звонков"),
            BotCommand(command="important", description="Важные звонки"),
            BotCommand(command="settings", description="Настройки услуги"),
            BotCommand(command="call", description="Карточка: /call 12"),
        ]
    )
    me = await bot.get_me()
    logging.info("МТС бот @%s готов", me.username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
