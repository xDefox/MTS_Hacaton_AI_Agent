import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Токен от @BotFather
API_URL = "http://127.0.0.1:8000/api/v1/process_incoming_call"  # Твой FastAPI

bot = Bot(token=TOKEN)
dp = Dispatcher()


# Команда старт — имитация активации услуги в приложении МТС
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Услуга 'ИИ-Агент' активна", callback_data="status_on")
    builder.button(text="⚙️ Настройки сценариев", callback_data="settings")
    builder.adjust(1)

    await message.answer(
        "👋 **Добро пожаловать в МТС Умный Ассистент!**\n\n"
        "Ваш персональный ИИ-секретарь настроен. Когда вы заняты на совещаниях, я буду принимать звонки от неизвестных номеров, отсеивать спам и присылать вам важные сводки.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# Функция для отправки уведомления о звонке (ее будет вызывать твой бэкенд или симулятор)
async def send_call_alert(chat_id: int, phone: str, summary: str, is_critical: bool, ai_response: str):
    builder = InlineKeyboardBuilder()

    if is_critical:
        alert_prefix = "⚠️ **ВАЖНЫЙ ЗВОНОК!**"
        builder.button(text="📞 Перезвонить срочно", callback_data=f"call_back_{phone}")
    else:
        alert_prefix = "ℹ️ **Входящий вызов (обработан ботом)**"
        builder.button(text="📝 Посмотреть детали", callback_data=f"details_{phone}")

    text = (
        f"{alert_prefix}\n\n"
        f"📱 **Номер:** `{phone}`\n"
        f"📋 **Резюме ИИ:** {summary}\n"
        f"🤖 **Что ответил робот:** _{ai_response}_"
    )

    await bot.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode="Markdown")


# Симуляция входящего звонка прямо из бота (для быстрой демонстрации жюри)
@dp.message(Command("simulate_call"))
async def simulate_call(message: types.Message):
    # Пример данных, которые прилетают от симулятора звонка
    payload = {
        "call_id": "call_12345",
        "caller_phone": "+375 (29) 555-35-35",
        "transcript_text": "Здравствуйте, мне срочно нужно купить партию вашего софта, перезвоните мне."
    }

    try:
        # Отправляем запрос на твой FastAPI бэкенд
        response = requests.post(API_URL, json=payload)
        data = response.json()

        # Отправляем карточку отчета в чат Ивану
        await send_call_alert(
            chat_id=message.chat.id,
            phone=payload["caller_phone"],
            summary=data["summary"],
            is_critical=data["is_critical"],
            ai_response=data["ai_response"]
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка соединения с FastAPI бэкендом: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())