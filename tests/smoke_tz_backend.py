"""Smoke без Ollama: правила, сценарии, hotline, stats, notify."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import CallRequest, CallResponse, Intent, Priority, ActionRequired
from backend.services.call_agent import apply_routing_rules
from backend.services.routing_rules import list_rules, match_rule
from backend.services.scenarios import list_scenarios
from backend.services.telegram_notify import notify_ivan_if_needed
from backend.services.yandex_llm import ensure_ai_disclosure


def test_rules_and_scenarios_seed():
    rules = list_rules()
    scenarios = list_scenarios()
    assert len(rules) >= 3
    assert any(s["kind"] == "greeting" for s in scenarios)
    spam = match_rule("Хотим предложить услуги по Директу со скидкой")
    assert spam is not None
    assert spam.is_critical is False
    human = match_rule("Соедините с менеджером пожалуйста")
    assert human is not None
    assert human.action_required == "transfer_to_human"
    print("OK rules/scenarios")


def test_apply_routing_rules_downgrades_spam():
    req = CallRequest(
        session_id="smoke-rules",
        user_message="Предлагаем услуги Директа со скидкой",
    )
    bad = CallResponse(
        agent_response=ensure_ai_disclosure("Перевожу на Ивана"),
        is_critical=True,
        priority=Priority.critical,
        intent=Intent.commercial,
        action_required=ActionRequired.transfer_to_human,
        summary="bad",
        recommended_next_step="call",
        session_id="smoke-rules",
        model="test",
    )
    fixed = apply_routing_rules(req, bad)
    assert fixed.is_critical is False
    assert fixed.action_required == ActionRequired.continue_dialog
    assert fixed.intent == Intent.spam
    print("OK apply_routing_rules")


async def _notify_async():
    resp = CallResponse(
        agent_response="x",
        is_critical=True,
        priority=Priority.high,
        intent=Intent.commercial,
        action_required=ActionRequired.callback_recommended,
        summary="Клиент хочет КП на интеграцию",
        recommended_next_step="Перезвонить",
        session_id="smoke-notify",
        model="test",
        call_id=1,
    )
    result = await notify_ivan_if_needed(resp, caller_phone="+7999")
    assert result["notified"] is True
    assert Path(result["local_file"]).is_file()
    print("OK notify jsonl")


def test_api_hotline_stats():
    client = TestClient(app)
    r = client.post(
        "/api/v1/hotline",
        json={"session_id": f"hl-{uuid.uuid4().hex[:8]}", "user_message": "Нужен человек", "client_phone": "+7000"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["action_required"] == "transfer_to_human"
    assert body["is_critical"] is True
    assert "искусственным интеллектом" in body["agent_response"].lower()

    s = client.get("/api/v1/stats")
    assert s.status_code == 200
    assert "total_calls" in s.json()

    rules = client.get("/api/v1/routing_rules")
    assert rules.status_code == 200
    assert rules.json()["total"] >= 1

    sc = client.get("/api/v1/scenarios")
    assert sc.status_code == 200
    print("OK api hotline/stats/rules/scenarios")


def main():
    test_rules_and_scenarios_seed()
    test_apply_routing_rules_downgrades_spam()
    import asyncio

    asyncio.run(_notify_async())
    test_api_hotline_stats()
    print("ALL TZ smoke OK (no Ollama)")


if __name__ == "__main__":
    main()
