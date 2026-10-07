#!/usr/bin/env python3
"""Контракт LLM-слоя без Ollama: parse, history, mock process_call, /ready, stats."""

from __future__ import annotations

import asyncio
import json
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
from backend.config import get_settings  # noqa: E402
from backend.prompts.system_ivan import build_system_prompt  # noqa: E402
from backend.services.call_agent import process_incoming_call  # noqa: E402
from backend.services.local_llm import (  # noqa: E402
    _extract_json_text,
    process_call_with_ollama,
)
from backend.services.routing_rules import reset_rules_to_defaults  # noqa: E402
from backend.services.yandex_llm import (  # noqa: E402
    _build_messages,
    _parse_output,
    ensure_ai_disclosure,
)


def _ok_json(**overrides) -> str:
    data = {
        "agent_response": "Здравствуйте, чем могу помочь?",
        "is_critical": False,
        "priority": "normal",
        "intent": "faq",
        "action_required": "continue_dialog",
        "summary": "FAQ вопрос",
        "caller_name": "",
        "recommended_next_step": "Ничего",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def test_parse_and_extract() -> int:
    failed = 0
    print("=== parse / extract ===")
    # plain
    parsed = _parse_output(_ok_json())
    if parsed.intent != Intent.faq:
        print("FAIL plain parse")
        failed += 1
    else:
        print("OK   plain parse")

    # markdown fence
    fenced = "```json\n" + _ok_json(intent="spam", is_critical=False) + "\n```"
    extracted = _extract_json_text(fenced)
    parsed2 = _parse_output(extracted)
    if parsed2.intent != Intent.spam:
        print("FAIL fenced parse")
        failed += 1
    else:
        print("OK   fenced parse")

    # noise around json
    noisy = "Вот ответ:\n" + _ok_json(intent="commercial", is_critical=True) + "\nКонец"
    parsed3 = _parse_output(_extract_json_text(noisy))
    if parsed3.intent != Intent.commercial or not parsed3.is_critical:
        print("FAIL noisy parse")
        failed += 1
    else:
        print("OK   noisy parse")

    # empty strings must be filled (qwen2.5:3b habit)
    emptyish = _ok_json(summary="", recommended_next_step="", caller_name="")
    parsed_empty = _parse_output(emptyish)
    if not parsed_empty.summary.strip() or not parsed_empty.recommended_next_step.strip():
        print("FAIL empty-field coalesce", parsed_empty.summary, parsed_empty.recommended_next_step)
        failed += 1
    else:
        print("OK   empty-field coalesce")

    # truncated JSON (num_predict cut mid-string)
    truncated = (
        '{"agent_response":"Здравствуйте!","is_critical":false,"priority":"normal",'
        '"intent":"other","action_required":"continue_dialog","summary":"Звонок без '
    )
    try:
        parsed_tr = _parse_output(truncated)
        if not parsed_tr.agent_response:
            print("FAIL truncated repair empty")
            failed += 1
        else:
            print("OK   truncated JSON repair")
    except Exception as exc:  # noqa: BLE001
        print("FAIL truncated repair", exc)
        failed += 1

    # English prompt leakage → replace with Russian
    en_junk = _ok_json(
        summary="2-3 sentences for Ivan",
        recommended_next_step="concrete next step",
    )
    parsed_en = _parse_output(en_junk)
    if "sentences for" in parsed_en.summary.lower() or "concrete" in parsed_en.recommended_next_step.lower():
        print("FAIL en-junk sanitize", parsed_en.summary, parsed_en.recommended_next_step)
        failed += 1
    elif not any("а" <= c.lower() <= "я" or c.lower() == "ё" for c in parsed_en.summary):
        print("FAIL en-junk not russian", parsed_en.summary)
        failed += 1
    else:
        print("OK   en-junk sanitize")

    # disclosure dedupe
    raw = ensure_ai_disclosure(
        "Внимание: вы общаетесь с искусственным интеллектом. Здравствуйте!"
    )
    if raw.lower().count("искусственным интеллектом") != 1:
        print("FAIL disclosure dedupe")
        failed += 1
    else:
        print("OK   disclosure dedupe")
    return failed


def test_dialog_history() -> int:
    failed = 0
    print("\n=== dialog_history ===")
    req = CallRequest(
        session_id="hist-1",
        user_message="А можно сегодня?",
        dialog_history=[
            {"role": "user", "text": "Интересует интеграция API"},
            {"role": "assistant", "text": "Уточните срок, пожалуйста"},
            {"role": "user", "text": ""},  # skip empty
            {"role": "tool", "text": "should-skip"},
        ],
    )
    msgs = _build_messages(req, "SYS")
    roles = [m["role"] for m in msgs]
    texts = [m["text"] for m in msgs]
    if msgs[0]["role"] != "system" or msgs[0]["text"] != "SYS":
        print("FAIL system first")
        failed += 1
    elif "user" not in roles or "assistant" not in roles:
        print("FAIL history roles", roles)
        failed += 1
    elif any("should-skip" in t for t in texts):
        print("FAIL tool role leaked")
        failed += 1
    elif "А можно сегодня?" not in texts[-1]:
        print("FAIL current message missing")
        failed += 1
    else:
        print("OK   dialog_history wiring")
    return failed


async def test_mocked_process_call() -> int:
    failed = 0
    print("\n=== mocked process_call ===")
    reset_rules_to_defaults()

    async def fake_ollama(request, settings=None):
        return CallResponse(
            agent_response="Сейчас переведу на специалиста.",
            is_critical=True,
            priority=Priority.critical,
            intent=Intent.escalation,
            action_required=ActionRequired.transfer_to_human,
            summary="bad",
            recommended_next_step="call",
            session_id=request.session_id,
            model="mock-ollama",
        )

    # spam must be downgraded by rules even if mock escalates
    with patch(
        "backend.services.call_agent.process_call_with_ollama",
        new=AsyncMock(side_effect=fake_ollama),
    ):
        spam = await process_incoming_call(
            CallRequest(
                session_id="mock-spam",
                user_message="Предлагаем Директ со скидкой",
            )
        )
        human = await process_incoming_call(
            CallRequest(
                session_id="mock-human",
                user_message="Соедините с менеджером по договору",
            )
        )

    if spam.is_critical or spam.action_required != ActionRequired.continue_dialog:
        print(f"FAIL mock spam downgrade: {spam.is_critical} {spam.action_required}")
        failed += 1
    else:
        print("OK   mock spam downgrade")

    if not human.is_critical or human.action_required != ActionRequired.transfer_to_human:
        print(f"FAIL mock human: {human.is_critical} {human.action_required}")
        failed += 1
    else:
        print("OK   mock human escalate")

    # API path with mock
    client = TestClient(app)
    with patch(
        "backend.services.call_agent.process_call_with_ollama",
        new=AsyncMock(side_effect=fake_ollama),
    ):
        resp = client.post(
            "/api/v1/process_call",
            json={
                "session_id": "api-mock-1",
                "user_message": "Расскажи стишок",
                "client_phone": "+7000",
            },
        )
    if resp.status_code != 200:
        print("FAIL api mock status", resp.text)
        failed += 1
    else:
        body = resp.json()
        if body.get("is_critical") or body.get("action_required") != "continue_dialog":
            print("FAIL api mock offtop", body)
            failed += 1
        elif "искусственным интеллектом" not in body.get("agent_response", "").lower():
            print("FAIL api mock disclosure", body.get("agent_response"))
            failed += 1
        else:
            print("OK   api mock offtop + disclosure")
        if not body.get("call_id"):
            print("FAIL api mock no call_id")
            failed += 1
        else:
            print("OK   api mock persisted")
    return failed


def test_ready_and_stats() -> int:
    failed = 0
    print("\n=== /ready + stats ===")
    reset_rules_to_defaults()
    client = TestClient(app)

    ready = client.get("/ready")
    if ready.status_code != 200:
        print("FAIL ready status", ready.text)
        failed += 1
    else:
        body = ready.json()
        if not body.get("ready"):
            print("FAIL ready core", body)
            failed += 1
        elif "setup_hint" not in body or not body["setup_hint"]:
            print("FAIL setup_hint")
            failed += 1
        else:
            print("OK   ready core", "demo_ready=", body.get("demo_ready"))

    # seed analytics
    client.post("/api/v1/hotline", json={"session_id": "st1", "user_message": "человек"})
    with patch(
        "backend.services.call_agent.process_call_with_ollama",
        new=AsyncMock(
            side_effect=lambda request, settings=None: CallResponse(
                agent_response=ensure_ai_disclosure("ок"),
                is_critical=False,
                priority=Priority.low,
                intent=Intent.spam,
                action_required=ActionRequired.continue_dialog,
                summary="spam",
                recommended_next_step="ignore",
                session_id=request.session_id,
                model="mock",
            )
        ),
    ):
        client.post(
            "/api/v1/process_call",
            json={"session_id": "st2", "user_message": "Предлагаем Директ со скидкой"},
        )

    stats = client.get("/api/v1/stats")
    if stats.status_code != 200:
        print("FAIL stats", stats.text)
        failed += 1
    else:
        data = stats.json()
        if data.get("total_calls", 0) < 1:
            print("FAIL stats empty", data)
            failed += 1
        elif "by_intent" not in data or "by_action" not in data:
            print("FAIL stats shape", data)
            failed += 1
        else:
            print("OK   stats shape total=", data["total_calls"])
    return failed


def test_fast_path_and_compact() -> int:
    failed = 0
    print("\n=== fast-path + compact prompt ===")
    reset_rules_to_defaults()
    from backend.services.training_examples import reset_examples_to_defaults, sync_default_examples

    reset_examples_to_defaults()
    sync_default_examples()
    compact = build_system_prompt(get_settings(), compact=True)
    low = compact.lower()
    if "sentences for ivan" in low or "concrete next step" in low:
        print("FAIL compact has english placeholders")
        failed += 1
    elif "секретар" not in low:
        print("FAIL compact missing secretary role")
        failed += 1
    elif "русск" not in low:
        print("FAIL compact missing russian requirement")
        failed += 1
    else:
        print("OK   compact prompt russian")
    if "reply:" not in compact:
        print("FAIL compact missing sample replies")
        failed += 1
    else:
        print("OK   compact sample replies")

    async def _run() -> CallResponse:
        settings = get_settings().model_copy(update={"ollama_rules_fast_path": True})
        return await process_call_with_ollama(
            CallRequest(
                session_id="fast-spam",
                user_message="Продаём контекстную рекламу, давайте подключим вас сегодня",
            ),
            settings=settings,
        )

    resp = asyncio.run(_run())
    if not str(resp.model).startswith("rules:"):
        print("FAIL fast-path model", resp.model)
        failed += 1
    elif _is_bad_summary(resp.summary) or _is_bad_summary(resp.recommended_next_step):
        print("FAIL fast-path russian fields", resp.summary, resp.recommended_next_step)
        failed += 1
    elif resp.action_required != ActionRequired.continue_dialog:
        print("FAIL fast-path action", resp.action_required)
        failed += 1
    else:
        print("OK   fast-path spam (opt-in)", resp.model)

    # lite prompt helper exists and stays short
    from backend.services.local_llm import _lite_system_prompt
    from backend.services.routing_rules import match_rule

    rule = match_rule("Продаём контекстную рекламу сегодня")
    if rule is None:
        print("FAIL lite rule match")
        failed += 1
    else:
        lite = _lite_system_prompt(rule)
        if len(lite) > 900:
            print("FAIL lite prompt too long", len(lite))
            failed += 1
        else:
            print("OK   lite prompt size", len(lite))
    return failed


def _is_bad_summary(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    return not any("а" <= c.lower() <= "я" or c.lower() == "ё" for c in t)


def main() -> None:
    failed = 0
    failed += test_parse_and_extract()
    failed += test_dialog_history()
    failed += asyncio.run(test_mocked_process_call())
    failed += test_ready_and_stats()
    failed += test_fast_path_and_compact()
    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL LLM CONTRACT CHECKS OK (no Ollama)")


if __name__ == "__main__":
    main()
