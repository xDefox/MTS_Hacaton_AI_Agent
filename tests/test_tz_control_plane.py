#!/usr/bin/env python3
"""ТЗ control-plane: notifications, audit, training examples + TTS offline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.prompts.system_ivan import build_system_prompt  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.services.access_audit import log_access, list_access_audit  # noqa: E402
from backend.services.training_examples import (  # noqa: E402
    examples_prompt_block,
    list_examples,
    upsert_example,
    delete_example,
)


def main() -> None:
    client = TestClient(app)
    failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failed
        if cond:
            print(f"OK   {name}")
        else:
            failed += 1
            print(f"FAIL {name}: {detail}")

    # seed notification via hotline
    line = "79001110001"
    hl = client.post(
        "/api/v1/hotline",
        json={
            "session_id": "ctrl-hl",
            "user_message": "нужен человек",
            "line_phone": line,
            "client_phone": "+7111",
        },
    )
    check("hotline", hl.status_code == 200, hl.text)
    call_id = (hl.json() or {}).get("call_id")

    notes = client.get("/api/v1/notifications")
    check("notifications-200", notes.status_code == 200, notes.text)
    check("notifications-nonempty", notes.json().get("total", 0) >= 1, notes.text)

    # audit via view
    if isinstance(call_id, int):
        client.get(f"/api/v1/calls/{call_id}", params={"phone": line})
    audit = client.get("/api/v1/audit")
    check("audit-200", audit.status_code == 200, audit.text)
    check("audit-nonempty", audit.json().get("total", 0) >= 1, audit.text)
    actions = {i.get("action") for i in audit.json().get("items", [])}
    check("audit-has-view", "view_call" in actions or "correct_call" in actions, str(actions))

    # training examples CRUD + prompt injection
    ex = client.get("/api/v1/training_examples")
    check("training-list", ex.status_code == 200 and ex.json()["total"] >= 1, ex.text)
    put = client.put(
        "/api/v1/training_examples",
        json={
            "id": "ex-test-tmp",
            "user_message": "UNIQUE_TRAIN_TOKEN_99",
            "expected_intent": "faq",
            "expected_action": "continue_dialog",
            "note": "tmp",
            "enabled": True,
        },
    )
    check("training-put", put.status_code == 200, put.text)
    prompt = build_system_prompt(get_settings())
    check("training-in-prompt", "UNIQUE_TRAIN_TOKEN_99" in prompt, prompt[-400:])
    check("training-block-helper", "UNIQUE_TRAIN_TOKEN_99" in examples_prompt_block(), "")
    delete = client.delete("/api/v1/training_examples/ex-test-tmp")
    check("training-delete", delete.status_code == 200, delete.text)

    # local TTS (no Ollama) via synthesize API
    syn = client.post(
        "/api/v1/synthesize",
        json={"text": "Тест озвучки для Ивана. Это проверка локального TTS."},
    )
    check("synthesize-200", syn.status_code == 200, syn.text)
    syn_body = syn.json() if syn.status_code == 200 else {}
    check("synthesize-engine-local", "local" in (syn_body.get("engine") or "").lower()
          or "pyttsx" in (syn_body.get("engine") or "").lower()
          or syn_body.get("filename"), str(syn_body))
    check("synthesize-file", bool(syn_body.get("filename") or syn_body.get("audio_url")), str(syn_body))

    # unit audit helper
    log_access("test_action", call_id=999, detail="suite")
    rows = list_access_audit(limit=5)
    check("audit-helper", any(r.get("action") == "test_action" for r in rows), str(rows[:2]))

    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL TZ CONTROL-PLANE CHECKS OK")


if __name__ == "__main__":
    main()
