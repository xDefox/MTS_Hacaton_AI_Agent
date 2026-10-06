#!/usr/bin/env python3
"""Жёсткие кейсы маршрутизации: оффтоп/спам НЕ к специалисту; эскалация — только по делу."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas import ActionRequired, CallRequest  # noqa: E402
from backend.services.call_agent import process_incoming_call  # noqa: E402

MUST_NOT_ESCALATE = [
    CallRequest(
        session_id="hard-rhyme",
        client_phone="+79001110001",
        user_message="Расскажи мне стишок, пожалуйста",
    ),
    CallRequest(
        session_id="hard-cold-sales",
        client_phone="+79001110002",
        user_message=(
            "Здравствуйте, мы продаём продвижение в Директе и хотим предложить вам услуги со скидкой"
        ),
    ),
    CallRequest(
        session_id="hard-chat",
        client_phone="+79001110003",
        user_message="Давай просто поболтаем, мне скучно",
    ),
    CallRequest(
        session_id="hard-joke",
        client_phone="+79001110005",
        user_message="Расскажи анекдот про программистов",
    ),
]

MUST_ESCALATE = [
    CallRequest(
        session_id="hard-human",
        client_phone="+79001110004",
        user_message="Соедините с менеджером, срочно по договору!",
    ),
]

MUST_BE_CRITICAL_LEAD = [
    CallRequest(
        session_id="hard-lead",
        client_phone="+79001112233",
        user_message=(
            "Добрый день, меня зовут Алексей из компании Альфа. "
            "Интересует интеграция вашего API, нужен ответ по пилоту до пятницы."
        ),
    ),
]


async def _run(req: CallRequest):
    print(f"--- {req.session_id} ---")
    print(f"IN: {req.user_message}")
    resp = await process_incoming_call(req)
    print(
        f"OUT: critical={resp.is_critical} intent={resp.intent} "
        f"action={resp.action_required} model={resp.model}"
    )
    print(f"agent: {resp.agent_response[:200]}")
    print()
    return resp


async def main() -> None:
    print("=== Hard routing (YandexGPT + guard) ===\n")
    failed = 0

    for req in MUST_NOT_ESCALATE:
        resp = await _run(req)
        bad = (
            resp.action_required == ActionRequired.transfer_to_human
            or resp.is_critical
        )
        if bad:
            print(f"FAIL {req.session_id}: junk escalated/critical\n")
            failed += 1
        else:
            print(f"OK {req.session_id}: not escalated\n")

    for req in MUST_ESCALATE:
        resp = await _run(req)
        if resp.action_required != ActionRequired.transfer_to_human:
            print(f"FAIL {req.session_id}: expected transfer_to_human\n")
            failed += 1
        else:
            print(f"OK {req.session_id}: escalated\n")

    for req in MUST_BE_CRITICAL_LEAD:
        resp = await _run(req)
        if not resp.is_critical:
            print(f"FAIL {req.session_id}: lead should be critical\n")
            failed += 1
        elif resp.action_required == ActionRequired.transfer_to_human:
            print(f"FAIL {req.session_id}: lead should callback, not human by default\n")
            failed += 1
        else:
            print(f"OK {req.session_id}: critical lead\n")

    if failed:
        print(f"FAILED checks: {failed}")
        raise SystemExit(1)
    print("ALL HARD CHECKS OK")


if __name__ == "__main__":
    asyncio.run(main())
