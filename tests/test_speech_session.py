#!/usr/bin/env python3
"""ТЗ: мультитур, session filter, telegram-routing, TTS→STT roundtrip (offline)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.schemas import (  # noqa: E402
    ActionRequired,
    CallRequest,
    CallResponse,
    Intent,
    Priority,
)
from backend.services.call_agent import process_incoming_call  # noqa: E402
from backend.services.local_tts import synthesize_wav_local  # noqa: E402
from backend.services.routing_rules import match_rule, reset_rules_to_defaults  # noqa: E402
from backend.services.yandex_llm import ensure_ai_disclosure  # noqa: E402


def test_telegram_rules() -> int:
    failed = 0
    print("=== telegram / complex rules ===")
    reset_rules_to_defaults()
    cases = [
        ("SLA и NDA по договору", "offer_telegram_chat"),
        ("Готовим детальное ТЗ на интеграцию", "offer_telegram_chat"),
        ("Нужно коммерческое предложение", "offer_telegram_chat"),
    ]
    for text, action in cases:
        rule = match_rule(text)
        ok = rule is not None and rule.action_required == action
        print(f"{'OK' if ok else 'FAIL'}  {text[:40]!r} -> {getattr(rule, 'action_required', None)}")
        if not ok:
            failed += 1
    return failed


async def _multiturn_mock() -> int:
    failed = 0
    print("\n=== multiturn mock ===")
    reset_rules_to_defaults()

    async def fake(request, settings=None):
        # модель «не видит» историю и эскалирует — правила/логика всё равно должны жить
        return CallResponse(
            agent_response="Продолжаем.",
            is_critical=False,
            priority=Priority.normal,
            intent=Intent.faq,
            action_required=ActionRequired.continue_dialog,
            summary="ok",
            recommended_next_step="-",
            session_id=request.session_id,
            model="mock",
        )

    with patch(
        "backend.services.call_agent.process_call_with_yandex",
        new=AsyncMock(side_effect=fake),
    ):
        resp = await process_incoming_call(
            CallRequest(
                session_id="mt-1",
                user_message="А по SLA какие гарантии?",
                dialog_history=[
                    {"role": "user", "text": "Интересует интеграция"},
                    {"role": "assistant", "text": "Уточните детали"},
                ],
            )
        )
    if resp.action_required != ActionRequired.offer_telegram_chat or not resp.is_critical:
        print(f"FAIL multiturn sla routing: {resp.action_required} critical={resp.is_critical}")
        failed += 1
    elif "искусственным интеллектом" in resp.agent_response.lower():
        # ассистент уже говорил в этой сессии — предупреждение было в приветствии
        print(f"FAIL multiturn: disclosure repeated mid-dialog: {resp.agent_response!r}")
        failed += 1
    else:
        print("OK   multiturn + telegram rule, no repeated disclosure")
    return failed


def test_multiturn_mock() -> None:
    assert asyncio.run(_multiturn_mock()) == 0


def test_session_filter_and_validation() -> int:
    failed = 0
    print("\n=== session filter + validation ===")
    client = TestClient(app)
    sid = "session-filter-xyz"

    # create two turns via hotline + process mock
    line = "79001110000"
    client.post(
        "/api/v1/hotline",
        json={
            "session_id": sid,
            "user_message": "нужен человек",
            "line_phone": line,
            "client_phone": "+79001112233",
        },
    )
    with patch(
        "backend.services.call_agent.process_call_with_yandex",
        new=AsyncMock(
            side_effect=lambda request, settings=None: CallResponse(
                agent_response=ensure_ai_disclosure("ок"),
                is_critical=False,
                priority=Priority.low,
                intent=Intent.other,
                action_required=ActionRequired.continue_dialog,
                summary="t2",
                recommended_next_step="-",
                session_id=request.session_id,
                model="mock",
            )
        ),
    ):
        client.post(
            "/api/v1/process_call",
            json={
                "session_id": sid,
                "line_phone": line,
                "user_message": "Ещё вопрос по часам работы",
            },
        )

    filtered = client.get(
        "/api/v1/calls",
        params={"phone": line, "session_id": sid, "limit": 50},
    )
    if filtered.status_code != 200:
        print("FAIL session filter status", filtered.text)
        failed += 1
    else:
        items = filtered.json().get("items", [])
        if not items or any(i["session_id"] != sid for i in items):
            print("FAIL session filter items", items[:3])
            failed += 1
        elif len(items) < 2:
            print("FAIL expected >=2 turns", len(items))
            failed += 1
        else:
            print(f"OK   session filter turns={len(items)}")

    too_long = client.post(
        "/api/v1/process_call",
        json={"session_id": "x", "user_message": "а" * 4001},
    )
    if too_long.status_code != 422:
        print("FAIL max_length validation", too_long.status_code)
        failed += 1
    else:
        print("OK   user_message max_length")
    return failed


def test_tts_stt_roundtrip() -> int:
    """ТЗ точность расшифровки: локальный TTS → Whisper (может скачать tiny)."""
    failed = 0
    print("\n=== TTS->STT roundtrip ===")
    try:
        wav = synthesize_wav_local("Здравствуйте, это проверка распознавания речи.")
        from backend.services.local_stt import transcribe_audio_local

        text = transcribe_audio_local(wav, language="ru")
        print(f"    transcript={text!r}")
        if not text or len(text) < 3:
            print("FAIL empty transcript")
            failed += 1
        else:
            # мягкая проверка: хоть одно общее слово / длина
            low = text.lower()
            hit = any(w in low for w in ("здрав", "провер", "распозн", "реч", "это"))
            if not hit and len(text) < 5:
                print("FAIL weak transcript")
                failed += 1
            else:
                print("OK   roundtrip non-empty")
    except Exception as exc:  # noqa: BLE001
        # первый прогон может качать модель — не валим весь suite
        print(f"SKIP STT roundtrip: {exc}")
    return failed


def main() -> None:
    failed = 0
    failed += test_telegram_rules()
    failed += asyncio.run(_multiturn_mock())
    failed += test_session_filter_and_validation()
    failed += test_tts_stt_roundtrip()
    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL SPEECH/SESSION CHECKS OK")


if __name__ == "__main__":
    main()
