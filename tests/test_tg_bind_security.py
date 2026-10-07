"""Привязка Telegram: только из приложения МТС, 1 chat → 1 линия."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import telegram_notify as tg


client = TestClient(app)


def test_subscribe_without_token_forbidden():
    resp = client.post(
        "/api/v1/telegram/subscribe",
        json={"chat_id": 111001, "bind_token": "", "phone": "79001112233"},
    )
    assert resp.status_code == 403


def test_subscribe_fake_token_rejected():
    resp = client.post(
        "/api/v1/telegram/subscribe",
        json={"chat_id": 111002, "bind_token": "b_fake_token_xxx", "phone": "79001112233"},
    )
    assert resp.status_code == 400


def test_register_then_subscribe_one_chat_one_line(tmp_path, monkeypatch):
    monkeypatch.setattr(tg, "LINES_PATH", tmp_path / "tg_lines.json")

    phone_a = "79005550101"
    phone_b = "79005550102"
    tg.register_line(phone_a)
    token_a = tg.bind_token_for_phone(phone_a)
    assert token_a.startswith("b")

    ok = client.post(
        "/api/v1/telegram/subscribe",
        json={"chat_id": 222001, "bind_token": token_a, "phone": ""},
    )
    assert ok.status_code == 200
    assert ok.json().get("activated") is True
    assert tg.phone_for_chat(222001) == phone_a

    # тот же токен второй раз — мёртв
    again = client.post(
        "/api/v1/telegram/subscribe",
        json={"chat_id": 222099, "bind_token": token_a, "phone": ""},
    )
    assert again.status_code == 400

    # тот же chat_id на другую линию — предыдущая линия гасится
    tg.register_line(phone_b)
    token_b = tg.bind_token_for_phone(phone_b)
    swap = client.post(
        "/api/v1/telegram/subscribe",
        json={"chat_id": 222001, "bind_token": token_b, "phone": ""},
    )
    assert swap.status_code == 200
    assert tg.phone_for_chat(222001) == phone_b
