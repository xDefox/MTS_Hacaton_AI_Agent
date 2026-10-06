#!/usr/bin/env python3
"""Smoke scenarios for checkpoint 1 (no server required — calls LLM service directly)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Allow `python tests/smoke_test.py` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas import CallRequest  # noqa: E402
from backend.services.yandex_llm import process_call_with_yandex  # noqa: E402

SCENARIOS = [
    CallRequest(
        session_id="smoke-commercial",
        client_phone="+79001112233",
        user_message=(
            "Добрый день, меня зовут Алексей из компании Альфа. "
            "Интересует интеграция вашего API, нужен ответ по пилоту до пятницы."
        ),
    ),
    CallRequest(
        session_id="smoke-spam",
        client_phone="+79005556677",
        user_message="Здравствуйте! Предлагаем услуги продвижения в Директе со скидкой 40%.",
    ),
    CallRequest(
        session_id="smoke-escalation",
        client_phone="+79008889900",
        user_message="Соедините с менеджером, срочно по договору!",
    ),
]


async def main() -> None:
    print("=== Checkpoint 1 smoke test (YandexGPT) ===\n")
    for req in SCENARIOS:
        print(f"--- {req.session_id} ---")
        print(f"IN: {req.user_message}")
        resp = await process_call_with_yandex(req)
        print(json.dumps(resp.model_dump(), ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    asyncio.run(main())
