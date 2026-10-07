"""Тексты и клавиатуры дашборда Ивана в Telegram (ТЗ: контроль и история)."""

from __future__ import annotations

import html
from collections import Counter

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from backend.services.telegram_notify import format_phone

BTN_DASH = "Дашборд"
BTN_ALL = "Все звонки"
BTN_CRIT = "Важные"
BTN_SET = "Настройки"
BTN_CALL = "📞 Начать звонок"
BTN_HANGUP = "⏹ Завершить звонок"

DEFAULT_GREETING = (
    "Здравствуйте! Вы говорите с виртуальным ассистентом. Чем могу помочь?"
)

INTENT_RU = {
    "commercial": "Коммерция",
    "support_request": "Поддержка",
    "complaint": "Жалоба",
    "faq": "FAQ",
    "partnership": "Партнёрство",
    "spam": "Спам",
    "wrong_number": "Ошиблись номером",
    "escalation": "Эскалация",
    "other": "Другое",
}
ACTION_RU = {
    "continue_dialog": "Диалог",
    "transfer_to_human": "Человек",
    "offer_telegram_chat": "В чат",
    "callback_recommended": "Перезвонить",
}
PRIORITY_RU = {
    "critical": "критичный",
    "high": "высокий",
    "normal": "обычный",
    "low": "низкий",
}
MODE_RU = {
    "strict": "Строгий — только важные в пуш",
    "loyal": "Лояльный — пропускать рутину в пуш",
}


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CALL)],
            [KeyboardButton(text=BTN_DASH), KeyboardButton(text=BTN_ALL)],
            [KeyboardButton(text=BTN_CRIT), KeyboardButton(text=BTN_SET)],
        ],
        resize_keyboard=True,
    )


def call_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура во время эмуляции входящего звонка."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_HANGUP)]],
        resize_keyboard=True,
    )


_DISCLOSURE_ONCE = (
    "Внимание: вы общаетесь с искусственным интеллектом. "
    "Разговор может записываться для передачи информации владельцу. "
)


def demo_greeting_text(prefs: dict) -> str:
    """Приветствие для демо-звонка: disclosure один раз + шаблон линии."""
    if prefs.get("scenarios"):
        greet = (prefs.get("template_greeting") or "").strip()
    else:
        greet = ""
    body = greet or DEFAULT_GREETING
    lower = body.lower()
    if "искусственным интеллектом" in lower or "общаетесь с ии" in lower:
        return body
    return f"{_DISCLOSURE_ONCE}{body}"


def format_call_turn(payload: dict) -> str:
    """Краткий текст реплики после ответа агента (для чата рядом с ГС)."""
    flag = "⚠️" if payload.get("is_critical") else "•"
    cid = payload.get("call_id") or payload.get("id") or "—"
    transcript = html.escape(_clip(str(payload.get("transcript") or ""), 200))
    reply = html.escape(_clip(str(payload.get("agent_response") or "—"), 350))
    summary = html.escape(_clip(str(payload.get("summary") or "—"), 180))
    action = _action(payload.get("action_required"))
    lines = [
        f"{flag} <b>Реплика #{cid}</b>",
        f"Вы: {transcript or '—'}",
        f"Агент: {reply}",
        f"Резюме: {summary}",
        f"Действие: {action}",
    ]
    return "\n".join(lines)


def history_keyboard(items: list[dict], *, critical: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'⚠️' if item.get('is_critical') else '•'} #{item.get('id')} открыть",
                callback_data=f"call:{item.get('id')}",
            )
        ]
        for item in items[:8]
        if item.get("id") is not None
    ]
    rows.append(
        [
            InlineKeyboardButton(text="Все", callback_data="hist:all"),
            InlineKeyboardButton(text="Важные", callback_data="hist:crit"),
            InlineKeyboardButton(text="Дашборд", callback_data="dash"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard() -> InlineKeyboardMarkup:
    """Настройки меняются во фронте — в боте только просмотр."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Дашборд", callback_data="dash")],
            [
                InlineKeyboardButton(text="Все", callback_data="hist:all"),
                InlineKeyboardButton(text="Важные", callback_data="hist:crit"),
            ],
        ]
    )


def _clip(text: str, limit: int = 160) -> str:
    text = (text or "—").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _when(raw) -> str:
    if not raw:
        return "—"
    return str(raw).replace("T", " ")[:16]


def _intent(raw) -> str:
    key = str(raw or "other")
    return INTENT_RU.get(key, key)


def _action(raw) -> str:
    key = str(raw or "")
    return ACTION_RU.get(key, key or "—")


def format_history(items: list[dict], *, critical: bool, total: int) -> str:
    title = "⚠️ Важные звонки" if critical else "📋 Все звонки"
    if not items:
        empty = "Важных обращений пока нет." if critical else "История пуста — звонков ещё не было."
        return f"<b>{title}</b>\n\n{empty}"
    lines = [f"<b>{title}</b>", f"Показано {len(items)} из {total}", ""]
    for item in items:
        flag = "⚠️" if item.get("is_critical") else "•"
        cid = item.get("id") or "—"
        phone = html.escape(format_phone(str(item.get("caller_phone") or "")))
        who = html.escape(str(item.get("caller_name") or "").strip())
        head = f"{flag} <b>#{cid}</b>  {phone}"
        if who:
            head += f" · {who}"
        lines.append(head)
        lines.append(
            f"{_when(item.get('created_at'))} · {_intent(item.get('intent'))} · "
            f"{PRIORITY_RU.get(str(item.get('priority') or ''), str(item.get('priority') or '—'))}"
        )
        lines.append(html.escape(_clip(str(item.get("summary") or "—"))))
        lines.append("")
    return "\n".join(lines).strip()


def format_detail(item: dict) -> str:
    flag = "⚠️ Важно" if item.get("is_critical") else "Звонок"
    caller = html.escape(format_phone(str(item.get("caller_phone") or "")))
    line = html.escape(format_phone(str(item.get("line_phone") or "")))
    who = html.escape(str(item.get("caller_name") or "").strip()) or "не представился"
    direction = "входящий" if (item.get("direction") or "inbound") == "inbound" else "исходящий"
    inbound = item.get("input") or item.get("user_message") or "—"
    outbound = item.get("output") or item.get("agent_response") or "—"
    lines = [
        f"<b>{flag} #{item.get('id')}</b>",
        f"Когда: {_when(item.get('created_at'))}",
        f"Линия: {line} · {direction}",
        f"Кто: {who}",
        f"Звонящий: {caller}",
        f"Намерение: {_intent(item.get('intent'))}",
        f"Приоритет: {PRIORITY_RU.get(str(item.get('priority') or ''), '—')}",
        f"Действие: {_action(item.get('action_required'))}",
        "",
        "<b>Резюме</b>",
        html.escape(str(item.get("summary") or "—")),
        "",
        "<b>Вход</b>",
        html.escape(_clip(str(inbound), 400)),
        "",
        "<b>Выход</b>",
        html.escape(_clip(str(outbound), 400)),
    ]
    step = str(item.get("recommended_next_step") or "").strip()
    if step:
        lines += ["", "<b>Дальше</b>", html.escape(step)]
    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    total = int(stats.get("total") or 0)
    critical = int(stats.get("critical") or 0)
    routine = int(stats.get("routine") or 0)
    share = stats.get("critical_share") or 0
    lines = [
        "<b>📊 МТС · Дашборд линии</b>",
        "",
        f"Всего карточек: <b>{total}</b>",
        f"Важные: <b>{critical}</b> ({share}%)",
        f"Рутина: {routine}",
    ]
    if total:
        lines += ["", "<b>По намерениям</b>"]
        for key, count in (stats.get("by_intent") or {}).items():
            lines.append(f"· {_intent(key)} — {count}")
        lines += ["", "<b>Что делать</b>"]
        for key, count in (stats.get("by_action") or {}).items():
            lines.append(f"· {_action(key)} — {count}")
        lines += ["", "<b>Приоритет</b>"]
        for key, count in (stats.get("by_priority") or {}).items():
            label = PRIORITY_RU.get(str(key), str(key))
            lines.append(f"· {label} — {count}")
    else:
        lines += ["", "Пока нет звонков — дашборд заполнится после process_call."]
    return "\n".join(lines)


def format_settings(phone: str, prefs: dict) -> str:
    routing_key = prefs.get("routing") or "voice"
    routing_map = {
        "voice": "голос",
        "chat": "текст",
        "hybrid": "гибрид",
    }
    routing = routing_map.get(routing_key, routing_key)
    notify = "все звонки" if prefs.get("notify") == "all" else "только важные"
    mode = MODE_RU.get(prefs.get("mode") or "strict", prefs.get("mode") or "—")
    on = lambda flag: "вкл" if prefs.get(flag) else "выкл"
    tpl = ""
    if prefs.get("scenarios"):
        greet = (prefs.get("template_greeting") or "").strip()
        if greet:
            tpl = f"\nПриветствие: {html.escape(greet[:120])}{'…' if len(greet) > 120 else ''}"
    return (
        "<b>⚙️ Настройки услуги</b>\n"
        f"Линия: {html.escape(phone)}\n\n"
        f"Способ ответа: {routing}\n"
        f"История и саммари: {on('history')}\n"
        f"Шаблоны: {on('scenarios')}{tpl}\n"
        f"Пуши: {notify}\n"
        f"Режим: {mode}\n\n"
        "Меняются в приложении МТС. Бот только читает — подключать его необязательно."
    )


def count_intents(items: list[dict]) -> Counter:
    return Counter(str(item.get("intent") or "other") for item in items)
