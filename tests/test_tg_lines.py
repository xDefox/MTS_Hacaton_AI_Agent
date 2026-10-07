"""Привязка Telegram chat_id к актуальной линии МТС."""

from backend.services import telegram_notify as tg


def test_phone_for_chat_prefers_latest_activated(tmp_path, monkeypatch):
    monkeypatch.setattr(tg, "LINES_PATH", tmp_path / "tg_lines.json")
    chat_id = 1941027100

    tg.activate_line("1111111111", chat_id)
    assert tg.phone_for_chat(chat_id) == "1111111111"

    tg.activate_line("2222222222", chat_id)
    assert tg.phone_for_chat(chat_id) == "2222222222"

    # старая линия больше не привязана к этому чату
    lines = tg._load_lines()
    assert lines["1111111111"]["chat_id"] is None
    assert lines["1111111111"]["activated"] is False
    assert lines["2222222222"]["activated"] is True


def test_history_setting_follows_active_line(tmp_path, monkeypatch):
    from backend.services import service_settings as svc

    monkeypatch.setattr(tg, "LINES_PATH", tmp_path / "tg_lines.json")
    monkeypatch.setattr(svc, "SETTINGS_PATH", tmp_path / "service_settings.json")

    chat_id = 42
    tg.activate_line("79001112233", chat_id)
    svc.update_settings("79001112233", history=False)

    phone = tg.phone_for_chat(chat_id)
    prefs = svc.get_settings(phone)
    assert prefs["history"] is False
