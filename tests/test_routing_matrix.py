#!/usr/bin/env python3
"""Детерминированные тесты матрицы маршрутизации — без Ollama."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas import (  # noqa: E402
    ActionRequired,
    CallRequest,
    CallResponse,
    Intent,
    Priority,
)
from backend.services.call_agent import apply_routing_rules  # noqa: E402
from backend.services.routing_rules import match_rule, reset_rules_to_defaults  # noqa: E402
from backend.services.yandex_llm import (  # noqa: E402
    _guard_non_business_escalation,
    ensure_ai_disclosure,
)
from tests.fixtures.routing_cases import cases_by_layer  # noqa: E402


def _bad_escalation(session_id: str) -> CallResponse:
    """Имитация ошибочного ответа LLM, который надо срезать."""
    return CallResponse(
        agent_response=ensure_ai_disclosure("Сейчас соединю со специалистом."),
        is_critical=True,
        priority=Priority.critical,
        intent=Intent.escalation,
        action_required=ActionRequired.transfer_to_human,
        summary="bad escalation",
        recommended_next_step="call human",
        session_id=session_id,
        model="test-bad",
    )


def _action_value(action) -> str:
    return action.value if hasattr(action, "value") else str(action)


def _intent_value(intent) -> str:
    return intent.value if hasattr(intent, "value") else str(intent)


def _check_expectations(case: dict, response: CallResponse) -> list[str]:
    errors: list[str] = []
    if "expect_critical" in case and response.is_critical != case["expect_critical"]:
        errors.append(
            f"critical={response.is_critical} expected={case['expect_critical']}"
        )
    action = _action_value(response.action_required)
    if "expect_action" in case and action != case["expect_action"]:
        errors.append(f"action={action} expected={case['expect_action']}")
    if "expect_action_in" in case and action not in case["expect_action_in"]:
        errors.append(f"action={action} not in {case['expect_action_in']}")
    if "forbid_action" in case and action == case["forbid_action"]:
        errors.append(f"forbidden action={action}")
    intent = _intent_value(response.intent)
    if "expect_intent" in case and intent != case["expect_intent"]:
        errors.append(f"intent={intent} expected={case['expect_intent']}")
    if "intent_in" in case and intent not in case["intent_in"]:
        errors.append(f"intent={intent} not in {case['intent_in']}")
    return errors


def test_rules_layer() -> int:
    reset_rules_to_defaults()
    failed = 0
    cases = cases_by_layer("rules")
    print(f"\n=== rules layer ({len(cases)}) ===")
    for case in cases:
        req = CallRequest(
            session_id=f"rules-{case['id']}",
            user_message=case["user_message"],
        )
        matched = match_rule(req.user_message)
        if matched is None:
            print(f"FAIL {case['id']}: no rule matched")
            failed += 1
            continue
        fixed = apply_routing_rules(req, _bad_escalation(req.session_id))
        errs = _check_expectations(case, fixed)
        if errs:
            print(f"FAIL {case['id']}: {'; '.join(errs)} (rule={matched.id})")
            failed += 1
        else:
            print(f"OK   {case['id']} via {matched.id}")
    return failed


def test_guard_layer() -> int:
    failed = 0
    cases = cases_by_layer("guard")
    print(f"\n=== guard layer ({len(cases)}) ===")
    for case in cases:
        req = CallRequest(
            session_id=f"guard-{case['id']}",
            user_message=case["user_message"],
        )
        # Сначала rules (как в проде), потом guard на «сыром» bad-ответе
        after_rules = apply_routing_rules(req, _bad_escalation(req.session_id))
        # Если правило уже срезало — ок; иначе guard должен срезать
        if after_rules.is_critical or _action_value(after_rules.action_required) == "transfer_to_human":
            fixed = _guard_non_business_escalation(req, after_rules)
        else:
            fixed = after_rules
        # Если rules не сработали — чистый guard на bad
        if fixed.is_critical or _action_value(fixed.action_required) == "transfer_to_human":
            fixed = _guard_non_business_escalation(req, _bad_escalation(req.session_id))
        errs = _check_expectations(case, fixed)
        if errs:
            print(f"FAIL {case['id']}: {'; '.join(errs)}")
            failed += 1
        else:
            print(f"OK   {case['id']}")
    return failed


def test_disclosure() -> int:
    print("\n=== disclosure ===")
    failed = 0
    samples = [
        "Здравствуйте, чем помочь?",
        "Внимание: вы общаетесь с искусственным интеллектом. Здравствуйте!",
        "Вы общаетесь с искусственным интеллектом. Разговор может записываться. Ок.",
    ]
    for i, raw in enumerate(samples):
        out = ensure_ai_disclosure(raw)
        count = out.lower().count("искусственным интеллектом")
        if count != 1:
            print(f"FAIL disclosure-{i}: count={count} text={out[:120]}")
            failed += 1
        elif not out.lower().startswith("внимание:"):
            print(f"FAIL disclosure-{i}: no canonical prefix")
            failed += 1
        else:
            print(f"OK   disclosure-{i}")
    return failed


def test_matrix_ids_unique() -> int:
    from tests.fixtures.routing_cases import all_case_ids

    ids = all_case_ids()
    if len(ids) != len(set(ids)):
        print("FAIL duplicate case ids")
        return 1
    print(f"\nOK   unique ids ({len(ids)} cases)")
    return 0


def main() -> None:
    reset_rules_to_defaults()
    failed = 0
    failed += test_matrix_ids_unique()
    failed += test_disclosure()
    failed += test_rules_layer()
    failed += test_guard_layer()
    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL ROUTING MATRIX CHECKS OK (no Ollama)")


if __name__ == "__main__":
    main()
