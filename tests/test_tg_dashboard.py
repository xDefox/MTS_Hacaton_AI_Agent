"""Тесты текстов дашборда бота (без Telegram API)."""

from frontend.tg_dashboard import format_detail, format_history, format_stats


def test_format_history_splits_critical_and_all():
    items = [
        {
            "id": 2,
            "caller_phone": "79001112233",
            "caller_name": "Анна",
            "is_critical": True,
            "intent": "commercial",
            "priority": "high",
            "summary": "Просит коммерческое предложение",
            "created_at": "2026-10-07T12:00:00",
        },
        {
            "id": 1,
            "caller_phone": "79005554433",
            "is_critical": False,
            "intent": "spam",
            "priority": "low",
            "summary": "Реклама",
            "created_at": "2026-10-07T11:00:00",
        },
    ]
    all_text = format_history(items, critical=False, total=2)
    assert "Все звонки" in all_text
    assert "#2" in all_text and "#1" in all_text
    assert "⚠️" in all_text
    crit_text = format_history([items[0]], critical=True, total=1)
    assert "Важные" in crit_text
    assert "#2" in crit_text
    empty = format_history([], critical=True, total=0)
    assert "Важных" in empty


def test_format_stats_and_detail():
    from frontend.tg_dashboard import format_settings

    stats = format_stats(
        {
            "total": 10,
            "critical": 3,
            "routine": 7,
            "critical_share": 30.0,
            "by_intent": {"commercial": 4, "spam": 2},
            "by_action": {"callback_recommended": 3},
            "by_priority": {"high": 3, "low": 7},
        }
    )
    assert "Дашборд" in stats
    assert "Важные: <b>3</b>" in stats
    assert "Коммерция" in stats
    assert "Перезвонить" in stats

    detail = format_detail(
        {
            "id": 7,
            "is_critical": True,
            "line_phone": "79009998877",
            "caller_phone": "79001112233",
            "caller_name": "Иван",
            "direction": "inbound",
            "intent": "escalation",
            "priority": "critical",
            "action_required": "transfer_to_human",
            "summary": "Просит человека",
            "input": "Соедините с человеком",
            "output": "Перевожу на менеджера",
            "recommended_next_step": "Взять трубку",
            "created_at": "2026-10-07T09:15:00",
        }
    )
    assert "Важно #7" in detail
    assert "Эскалация" in detail
    assert "Человек" in detail
    assert "Взять трубку" in detail
    assert "Вход" in detail and "Соедините с человеком" in detail
    assert "Выход" in detail and "Перевожу на менеджера" in detail

    text = format_settings(
        "+7 900 111-22-33",
        {
            "routing": "voice",
            "history": True,
            "scenarios": False,
            "hotline": True,
            "notify": "critical",
            "mode": "strict",
        },
    )
    assert "приложении МТС" in text
    assert "только важные" in text
    assert "Шаблоны: выкл" in text


def test_demo_greeting_and_call_turn():
    from frontend.tg_dashboard import (
        DEFAULT_GREETING,
        BTN_CALL,
        demo_greeting_text,
        format_call_turn,
        main_keyboard,
    )

    assert demo_greeting_text({"scenarios": False}) == DEFAULT_GREETING
    assert demo_greeting_text(
        {"scenarios": True, "template_greeting": "  Привет от линии!  "}
    ) == "Привет от линии!"
    assert BTN_CALL in [b.text for row in main_keyboard().keyboard for b in row]

    card = format_call_turn(
        {
            "call_id": 9,
            "is_critical": True,
            "transcript": "Нужен менеджер",
            "agent_response": "Соединяю с Иваном",
            "summary": "Эскалация",
            "action_required": "transfer_to_human",
        }
    )
    assert "#9" in card
    assert "Нужен менеджер" in card
    assert "Человек" in card


if __name__ == "__main__":
    test_format_history_splits_critical_and_all()
    test_format_stats_and_detail()
    test_demo_greeting_and_call_turn()
    print("ALL TESTS PASSED (3)")
