#!/usr/bin/env python3
"""Smoke: process 3 calls → history list has rows with correct critical flags."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app

SCENARIOS = [
    {
        "session_id": "hist-commercial",
        "client_phone": "+79001112233",
        "user_message": (
            "Добрый день, меня зовут Алексей из компании Альфа. "
            "Интересует интеграция вашего API, нужен ответ по пилоту до пятницы."
        ),
        "expect_critical": True,
    },
    {
        "session_id": "hist-spam",
        "client_phone": "+79005556677",
        "user_message": "Здравствуйте! Предлагаем услуги продвижения в Директе со скидкой 40%.",
        "expect_critical": False,
    },
    {
        "session_id": "hist-escalation",
        "client_phone": "+79008889900",
        "user_message": "Соедините с менеджером, срочно по договору!",
        "expect_critical": True,
    },
]


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        print("health:", health.json())
        assert health.status_code == 200

        created_ids: list[int] = []
        for scenario in SCENARIOS:
            payload = {
                "session_id": scenario["session_id"],
                "client_phone": scenario["client_phone"],
                "user_message": scenario["user_message"],
            }
            resp = client.post("/api/v1/process_call", json=payload)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            print(
                f"{scenario['session_id']}: critical={body['is_critical']} "
                f"intent={body['intent']} call_id={body.get('call_id')} model={body['model']}"
            )
            assert body.get("call_id") is not None
            created_ids.append(body["call_id"])

        all_calls = client.get("/api/v1/calls")
        assert all_calls.status_code == 200
        data = all_calls.json()
        print(f"history total={data['total']}")
        assert data["total"] >= 3

        critical = client.get("/api/v1/calls", params={"critical_only": True})
        assert critical.status_code == 200
        crit_data = critical.json()
        print(f"critical_only total={crit_data['total']}")
        assert crit_data["total"] >= 2
        assert all(item["is_critical"] for item in crit_data["items"])

        detail = client.get(f"/api/v1/calls/{created_ids[0]}")
        assert detail.status_code == 200
        print("detail ok:", detail.json()["session_id"], detail.json()["summary"][:80], "...")

    print("=== history smoke OK ===")


if __name__ == "__main__":
    main()
