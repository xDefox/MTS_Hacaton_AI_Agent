#!/usr/bin/env python3
"""Golden-set против LLM (Ollama). Без Ollama — skip с кодом 0."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings  # noqa: E402
from backend.schemas import CallRequest  # noqa: E402
from backend.services.call_agent import process_incoming_call  # noqa: E402
from backend.services.routing_rules import reset_rules_to_defaults  # noqa: E402
from tests.fixtures.routing_cases import cases_by_layer  # noqa: E402


async def ollama_available() -> bool:
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
        return resp.status_code < 500
    except Exception:  # noqa: BLE001
        return False


def _val(x) -> str:
    return x.value if hasattr(x, "value") else str(x)


def _check(case: dict, resp) -> list[str]:
    errors: list[str] = []
    if "expect_critical" in case and resp.is_critical != case["expect_critical"]:
        errors.append(f"critical={resp.is_critical} want={case['expect_critical']}")
    action = _val(resp.action_required)
    if "expect_action" in case and action != case["expect_action"]:
        errors.append(f"action={action} want={case['expect_action']}")
    if "expect_action_in" in case and action not in case["expect_action_in"]:
        errors.append(f"action={action} not in {case['expect_action_in']}")
    if "forbid_action" in case and action == case["forbid_action"]:
        errors.append(f"forbidden action={action}")
    intent = _val(resp.intent)
    if "expect_intent" in case and intent != case["expect_intent"]:
        errors.append(f"intent={intent} want={case['expect_intent']}")
    if "intent_in" in case and intent not in case["intent_in"]:
        errors.append(f"intent={intent} not in {case['intent_in']}")
    return errors


async def main() -> None:
    reset_rules_to_defaults()
    if not await ollama_available():
        print("SKIP: Ollama недоступна — golden LLM-слой пропущен")
        raise SystemExit(0)

    cases = cases_by_layer("llm")
    print(f"=== Hard routing LLM golden ({len(cases)}) ===\n")
    failed = 0
    for case in cases:
        req = CallRequest(
            session_id=f"llm-{case['id']}",
            client_phone="+79001110000",
            user_message=case["user_message"],
        )
        print(f"--- {case['id']} ---")
        print(f"IN: {req.user_message[:120]}")
        resp = await process_incoming_call(req)
        print(
            f"OUT: critical={resp.is_critical} intent={resp.intent} "
            f"action={resp.action_required} model={resp.model}"
        )
        errs = _check(case, resp)
        if errs:
            print(f"FAIL: {'; '.join(errs)}\n")
            failed += 1
        else:
            print("OK\n")

    if failed:
        print(f"FAILED checks: {failed}")
        raise SystemExit(1)
    print("ALL LLM GOLDEN CHECKS OK")


if __name__ == "__main__":
    asyncio.run(main())
