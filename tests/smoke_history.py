#!/usr/bin/env python3
"""Smoke: process_call → SQLite history → GET /calls (ТЗ: контроль)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app

LINE = "79001234567"

SCENARIOS = [
    {
        "session_id": "hist-commercial",
        "line_phone": LINE,
        "client_phone": "+79001112233",
        "user_message": (
            "Добрый день, меня зовут Алексей из компании Альфа. "
            "Интересует интеграция вашего API, нужен ответ по пилоту до пятницы."
        ),
    },
    {
        "session_id": "hist-spam",
        "line_phone": LINE,
        "client_phone": "+79005556677",
        "user_message": "Здравствуйте! Предлагаем услуги продвижения в Директе со скидкой 40%.",
    },
    {
        "session_id": "hist-escalation",
        "line_phone": LINE,
        "client_phone": "+79008889900",
        "user_message": "Соедините с менеджером, срочно по договору!",
    },
]


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        print("health:", health.json())

        created_ids: list[int] = []
        for scenario in SCENARIOS:
            resp = client.post("/api/v1/process_call", json=scenario)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body.get("call_id") is not None
            created_ids.append(body["call_id"])
            print(
                f"{scenario['session_id']}: call_id={body['call_id']} "
                f"critical={body['is_critical']} intent={body['intent']} model={body['model']}"
            )

        all_calls = client.get("/api/v1/calls", params={"phone": LINE})
        assert all_calls.status_code == 200
        data = all_calls.json()
        print(f"history total={data['total']}")
        assert data["total"] >= 3
        assert all(item.get("line_phone") == LINE for item in data["items"])
        assert all("input" in item and "output" in item for item in data["items"])

        # чужая линия — пусто
        other = client.get("/api/v1/calls", params={"phone": "79009998877"})
        assert other.status_code == 200
        assert other.json()["total"] == 0

        # ТЗ: Иван видит важные отдельно
        critical = client.get(
            "/api/v1/calls",
            params={"phone": LINE, "critical_only": True},
        )
        assert critical.status_code == 200
        crit = critical.json()
        print(f"critical_only total={crit['total']}")
        assert crit["total"] >= 2
        assert all(item["is_critical"] for item in crit["items"])

        # ТЗ: детали = резюме + вход/выход
        detail = client.get(
            f"/api/v1/calls/{created_ids[0]}",
            params={"phone": LINE},
        )
        assert detail.status_code == 200
        card = detail.json()
        assert card["summary"]
        assert card["input"] and card["output"]
        assert card["user_message"] == card["input"]
        print("detail ok:", card["session_id"], "| summary:", card["summary"][:100])

        missing = client.get("/api/v1/calls/999999", params={"phone": LINE})
        assert missing.status_code == 404
        # чужой телефон не видит карточку
        foreign = client.get(
            f"/api/v1/calls/{created_ids[0]}",
            params={"phone": "79009998877"},
        )
        assert foreign.status_code == 404

    print("=== history smoke OK (ТЗ: контроль / история) ===")


if __name__ == "__main__":
    main()
