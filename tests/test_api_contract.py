#!/usr/bin/env python3
"""API-контракт ТЗ без Ollama: health, CRUD, hotline, history, patch, stats."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.services.routing_rules import reset_rules_to_defaults  # noqa: E402


def main() -> None:
    reset_rules_to_defaults()
    client = TestClient(app)
    failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failed
        if cond:
            print(f"OK   {name}")
        else:
            failed += 1
            print(f"FAIL {name}: {detail}")

    # health
    h = client.get("/health")
    check("health-200", h.status_code == 200, h.text)
    body = h.json()
    check("health-local-llm", body.get("llm_provider") == "local", str(body))
    check("health-status", body.get("status") == "ok", str(body))

    # routing rules CRUD
    rules = client.get("/api/v1/routing_rules")
    check("rules-list", rules.status_code == 200 and rules.json()["total"] >= 1, rules.text)
    put = client.put(
        "/api/v1/routing_rules",
        json={
            "id": "rule-test-tmp",
            "name": "tmp",
            "description": "test",
            "keywords": ["xyzzy-test-token"],
            "is_critical": False,
            "intent": "other",
            "action_required": "continue_dialog",
            "enabled": True,
        },
    )
    check("rules-put", put.status_code == 200 and put.json()["id"] == "rule-test-tmp", put.text)
    delete = client.delete("/api/v1/routing_rules/rule-test-tmp")
    check("rules-delete", delete.status_code == 200, delete.text)

    # scenarios CRUD
    sc = client.get("/api/v1/scenarios")
    check("scenarios-list", sc.status_code == 200 and sc.json()["total"] >= 1, sc.text)
    sc_put = client.put(
        "/api/v1/scenarios",
        json={
            "id": "sc-test-tmp",
            "name": "tmp faq",
            "kind": "faq",
            "text": "Тестовый ответ FAQ",
            "enabled": True,
        },
    )
    check("scenarios-put", sc_put.status_code == 200, sc_put.text)
    sc_del = client.delete("/api/v1/scenarios/sc-test-tmp")
    check("scenarios-delete", sc_del.status_code == 200, sc_del.text)

    # hotline
    line = "79990001122"
    hl = client.post(
        "/api/v1/hotline",
        json={
            "session_id": "api-hl-1",
            "user_message": "Нужен человек срочно",
            "line_phone": line,
            "client_phone": "+79990001122",
        },
    )
    check("hotline-200", hl.status_code == 200, hl.text)
    hl_body = hl.json() if hl.status_code == 200 else {}
    check("hotline-critical", hl_body.get("is_critical") is True, str(hl_body))
    check(
        "hotline-action",
        hl_body.get("action_required") == "transfer_to_human",
        str(hl_body),
    )
    check(
        "hotline-disclosure",
        "искусственным интеллектом" in (hl_body.get("agent_response") or "").lower(),
        str(hl_body.get("agent_response")),
    )
    call_id = hl_body.get("call_id")
    check("hotline-call-id", isinstance(call_id, int), str(call_id))

    # history + patch
    if isinstance(call_id, int):
        one = client.get(f"/api/v1/calls/{call_id}", params={"phone": line})
        check("calls-get", one.status_code == 200, one.text)
        check("calls-input-output", "input" in one.json() and "output" in one.json(), one.text)
        patch = client.patch(
            f"/api/v1/calls/{call_id}",
            params={"phone": line},
            json={"summary": "Ручная правка для теста API"},
        )
        check("calls-patch", patch.status_code == 200, patch.text)
        check(
            "calls-patch-summary",
            (patch.json() or {}).get("summary") == "Ручная правка для теста API",
            str(patch.text),
        )
        lst = client.get(
            "/api/v1/calls",
            params={"phone": line, "critical_only": True, "limit": 20},
        )
        check("calls-list-critical", lst.status_code == 200, lst.text)
        ids = [i["id"] for i in lst.json().get("items", [])]
        check("calls-list-contains", call_id in ids, str(ids[:10]))

    # stats
    st = client.get("/api/v1/stats")
    check("stats-200", st.status_code == 200, st.text)
    check("stats-total", "total_calls" in st.json(), st.text)

    # validation: empty process_call body
    bad = client.post("/api/v1/process_call", json={})
    check("process_call-validation", bad.status_code == 422, str(bad.status_code))

    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL API CONTRACT CHECKS OK")


if __name__ == "__main__":
    main()
