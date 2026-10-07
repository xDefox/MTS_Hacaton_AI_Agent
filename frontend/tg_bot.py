"""Telegram-бот Ивана: /start — услуга активна на номере; /history и /settings — команды."""

import asyncio
import html
import logging
import os
import time
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommand
from dotenv import load_dotenv

from backend.services.telegram_notify import (
    activate_line,
    format_phone,
    last_pending_phone,
    normalize_phone,
    phone_for_chat,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TOKEN = (os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
if not TOKEN:
    raise SystemExit("Нет TG_BOT_TOKEN: положите токен в .env в корне репозитория")

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_settings = {
    "mode": "Строгий (только важные)",
}
_last_start: dict[int, float] = {}


def _line_phone(chat_id: int, start_args: str = "") -> str:
    return (
        normalize_phone(start_args)
        or phone_for_chat(chat_id)
        or last_pending_phone()
    )


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
    await message.answer(f"Услуга активна на номере {display}")


@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}/api/v1/calls", params={"limit": 8})
        if resp.status_code != 200:
            await message.answer("История недоступна: бэкенд не ответил.")
            return
        items = resp.json().get("items") or []
        if not items:
            await message.answer("История пуста — звонков ещё не было.")
            return
        lines = ["История звонков"]
        for item in items:
            flag = "⚠️" if item.get("is_critical") else "•"
            phone = html.escape(str(item.get("caller_phone") or "—"))
            summary = html.escape(str(item.get("summary") or "—"))
            lines.append(f"\n{flag} {phone}\n{summary}")
        await message.answer("\n".join(lines))
    except httpx.RequestError:
        await message.answer("Не удалось связаться с API. Запустите uvicorn на :8000.")


@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    phone = format_phone(phone_for_chat(message.chat.id) or last_pending_phone())
    await message.answer(
        "Настройки\n"
        f"Номер: {phone}\n"
        f"Режим: {user_settings['mode']}\n\n"
        "Сменить режим: /mode"
    )


@dp.message(Command("mode"))
async def cmd_mode(message: types.Message):
    if "Строгий" in user_settings["mode"]:
        user_settings["mode"] = "Лояльный (пропускать клиентов)"
    else:
        user_settings["mode"] = "Строгий (только важные)"
    await message.answer(f"Режим: {user_settings['mode']}")


async def main():
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Услуга активна на номере"),
            BotCommand(command="history", description="История звонков"),
            BotCommand(command="settings", description="Настройки"),
        ]
    )
    me = await bot.get_me()
    logging.info("Бот @%s: /start, /history, /settings", me.username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
