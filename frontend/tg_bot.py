"""Telegram-бот Ивана: /start = услуга подключена; отчёты шлёт бэкенд."""

import asyncio
import html
import logging
import os
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from backend.services.telegram_notify import add_subscriber

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TOKEN = (os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
if not TOKEN:
    raise SystemExit("Нет TG_BOT_TOKEN: положите токен в .env в корне репозитория")

SERVICE_NAME = "AI менеджер звонков"

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_settings = {
    "status": "🟢 Активен (Ловит спам)",
    "mode": "Строгий (Только важные)",
}
_last_start: dict[int, float] = {}


def _home_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Услуга активна", callback_data="status_toggle")
    builder.button(text="⚙️ Настройки сценариев", callback_data="settings_menu")
    builder.adjust(1)
    return builder.as_markup()


def _register_chat(chat_id: int) -> None:
    """Чтобы бэкенд знал, куда слать отчёты process_call / process_call_voice."""
    add_subscriber(chat_id)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    now = time.monotonic()
    if now - _last_start.get(chat_id, 0) < 3:
        return
    _last_start[chat_id] = now

    _register_chat(chat_id)
    await message.answer(
        f"✅ <b>Услуга подключена</b>\n\n"
        f"«{html.escape(SERVICE_NAME)}» принимает входящие. "
        f"Отчёт нейросети придёт сюда, когда на бэкенд поступит звонок "
        f"(<code>/process_call</code> или <code>/process_call_voice</code>).",
        reply_markup=_home_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "status_toggle")
async def toggle_status(callback: types.CallbackQuery):
    current = user_settings["status"]
    if "Активен" in current:
        user_settings["status"] = "⏸️ Приостановлен"
        new_text = (
            "🔴 <b>Услуга временно отключена.</b> "
            "ИИ-агент больше не перехватывает звонки."
        )
    else:
        user_settings["status"] = "🟢 Активен (Ловит спам)"
        new_text = (
            "🟢 <b>Услуга успешно активирована!</b> ИИ-агент снова на страже."
        )

    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Настройки сценариев", callback_data="settings_menu")
    builder.button(text="🔙 В главное меню", callback_data="back_home")
    builder.adjust(1)
    await callback.message.edit_text(
        new_text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "settings_menu")
async def settings_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сменить режим (Строгий / Мягкий)", callback_data="change_mode")
    builder.button(text="🔙 В главное меню", callback_data="back_home")
    builder.adjust(1)
    await callback.message.edit_text(
        "⚙️ <b>Панель управления ИИ-агентом</b>\n\n"
        f"• Статус: <code>{html.escape(user_settings['status'])}</code>\n"
        f"• Режим фильтрации: <code>{html.escape(user_settings['mode'])}</code>\n\n"
        "Выберите параметр для изменения:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "change_mode")
async def change_mode(callback: types.CallbackQuery):
    if user_settings["mode"] == "Строгий (Только важные)":
        user_settings["mode"] = "🤝 Лояльный (Пропускать клиентов)"
    else:
        user_settings["mode"] = "Строгий (Только важные)"
    await callback.answer(f"Режим изменен на: {user_settings['mode']}", show_alert=True)
    await settings_menu(callback)


@dp.callback_query(F.data == "back_home")
async def back_home(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"✅ <b>Услуга подключена</b>\n\n"
        f"«{html.escape(SERVICE_NAME)}» работает. Жду звонки с бэкенда.",
        reply_markup=_home_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


async def main():
    logging.info(
        "Бот слушает /start. Отчёты приходят только с бэкенда "
        "(process_call / process_call_voice)."
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
