import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests

TOKEN = "8628878694:AAFfJMsE7pqXNQ0dmLj9VoqUPyfRX1fS-kQ"  # Твой токен от @BotFather
API_URL = "http://127.0.0.1:8000/api/v1/process_call"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Локальный стейт для демонстрации настроек пользователя
user_settings = {
    "status": "🟢 Активен (Ловит спам)",
    "mode": "Строгий (Только важные)"
}


# Команда старт — главное меню
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Услуга 'ИИ-Агент' активна", callback_data="status_toggle")
    builder.button(text="⚙️ Настройки сценариев", callback_data="settings_menu")
    builder.button(text="🧪 Тест звонка", callback_data="trigger_sim")
    builder.adjust(1)

    await message.answer(
        "👋 **Добро пожаловать в МТС Умный Ассистент!**\n\n"
        "Ваш персональный ИИ-секретарь настроен. Когда вы заняты на совещаниях, я буду принимать звонки от неизвестных номеров, отсеивать спам и присылать вам важные сводки.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# Обработка нажатий на инлайн-кнопки
@dp.callback_query(F.data == "status_toggle")
async def toggle_status(callback: types.CallbackQuery):
    current = user_settings["status"]
    if "Активен" in current:
        user_settings["status"] = "⏸️️ Приостановлен"
        new_text = "🔴 **Услуга временно отключена.** ИИ-агент больше не перехватывает звонки."
    else:
        user_settings["status"] = "🟢 Активен (Ловит спам)"
        new_text = "🟢 **Услуга успешно активирована!** ИИ-агент снова на страже."

    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Настройки сценариев", callback_data="settings_menu")
    builder.button(text="🔙 В главное меню", callback_data="back_home")
    builder.adjust(1)

    await callback.message.edit_text(new_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "settings_menu")
async def settings_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сменить режим (Строгий / Мягкий)", callback_data="change_mode")
    builder.button(text="🔙 В главное меню", callback_data="back_home")
    builder.adjust(1)

    await callback.message.edit_text(
        f"⚙️ **Панель управления ИИ-агентом**\n\n"
        f"• Статус: `{user_settings['status']}`\n"
        f"• Режим фильтрации: `{user_settings['mode']}`\n\n"
        f"Выберите параметр для изменения:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
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
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Услуга 'ИИ-Агент' активна", callback_data="status_toggle")
    builder.button(text="⚙️ Настройки сценариев", callback_data="settings_menu")
    builder.button(text="🧪 Тест звонка", callback_data="trigger_sim")
    builder.adjust(1)

    await callback.message.edit_text(
        "👋 **МТС Умный Ассистент (Главное меню)**\n\n"
        "Выберите нужное действие:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()


# Универсальная функция отправки карточки звонка
async def send_call_alert(message_or_chat, phone: str, summary: str, is_critical: bool, ai_response: str):
    builder = InlineKeyboardBuilder()

    if is_critical:
        alert_prefix = "⚠️ **ВАЖНЫЙ ЗВОНОК!**"
        builder.button(text="📞 Перезвонить срочно", callback_data=f"call_back_{phone}")
    else:
        alert_prefix = "ℹ️ **Входящий вызов (спам отсеян)**"
        builder.button(text="📝 Посмотреть детали", callback_data=f"details_{phone}")

    builder.button(text="🔙 В главное меню", callback_data="back_home")
    builder.adjust(1)

    text = (
        f"{alert_prefix}\n\n"
        f"📱 **Номер:** `{phone}`\n"
        f"📋 **Резюме ИИ:** {summary}\n"
        f"🤖 **Что ответил робот:** _{ai_response}_"
    )

    if isinstance(message_or_chat, types.Message):
        await message_or_chat.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await bot.send_message(message_or_chat.id, text, reply_markup=builder.as_markup(), parse_mode="Markdown")


# Общая логика отправки запроса на бэкенд
async def execute_simulation(target_message: types.Message):
    payload = {
        "session_id": "session_hackathon_01",
        "client_phone": "+375 (29) 555-35-35",
        "user_message": "Здравствуйте, мне срочно нужно купить партию вашего софта, перезвоните мне до пятницы."
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            await send_call_alert(
                message_or_chat=target_message,
                phone=payload["client_phone"],
                summary=data["summary"],
                is_critical=data["is_critical"],
                ai_response=data["agent_response"]
            )
        else:
            await target_message.answer(f"⚠️ Ошибка бэкенда: {response.status_code} - {response.text}")
    except Exception as e:
        await target_message.answer(f"❌ Ошибка соединения с FastAPI бэкендом: {e}")


# Обработка нажатия на инлайн-кнопку «Тест звонка»
@dp.callback_query(F.data == "trigger_sim")
async def trigger_sim_callback(callback: types.CallbackQuery):
    await callback.message.answer("🧪 Запускаю симуляцию входящего звонка через бэкенд...")
    await execute_simulation(callback.message)
    await callback.answer()


# Обработка текстовой команды /simulate_call
@dp.message(Command("simulate_call"))
async def cmd_simulate(message: types.Message):
    await message.answer("🧪 Симуляция вызова запущена...")
    await execute_simulation(message)


async def main():
    print("Бот запущен и готов к работе...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())