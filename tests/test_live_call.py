#!/usr/bin/env python3
"""Живой звонок: страница /call и WebSocket-конвейер (STT/LLM/TTS подменены, без сети)."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.schemas import ActionRequired, CallResponse, Intent, Priority  # noqa: E402

DISCLOSURE = "искусственным интеллектом"
failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failed
    if ok:
        print(f"OK   {name}")
    else:
        failed += 1
        print(f"FAIL {name}: {detail}")


def _wav(seconds: float = 0.5) -> bytes:
    n = int(16000 * seconds)
    header = b"RIFF" + struct.pack("<I", 36 + n * 2) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16
    ) + b"data" + struct.pack("<I", n * 2)
    return header + b"\x00\x00" * n


def _receive_turn(ws) -> tuple[list[dict], bytes | None]:
    """Сообщения до голоса агента (или до audio_unavailable)."""
    events: list[dict] = []
    while True:
        msg = ws.receive()
        if msg.get("bytes"):
            return events, msg["bytes"]
        data = json.loads(msg["text"])
        events.append(data)
        if data["type"] == "audio_unavailable":
            return events, None


def main() -> None:
    client = TestClient(app)
    page = client.get("/call")
    check("страница /call отдаётся", page.status_code == 200 and "WebSocket" in page.text, str(page.status_code))

    transcripts = iter(["Сколько стоит сайт?", "", "Соедините с менеджером по договору"])

    async def fake_stt(audio, **kwargs):
        return next(transcripts), "mock-stt"

    seen_histories: list[list[dict]] = []

    async def fake_llm(request, settings=None):
        seen_histories.append(list(request.dialog_history or []))
        wants_human = "соедините" in request.user_message.lower()
        return CallResponse(
            agent_response="Соединяю с Иваном." if wants_human else "Сайт-визитка от 40 000 рублей.",
            is_critical=wants_human,
            priority=Priority.critical if wants_human else Priority.normal,
            intent=Intent.escalation if wants_human else Intent.faq,
            action_required=ActionRequired.transfer_to_human if wants_human else ActionRequired.continue_dialog,
            summary="s", recommended_next_step="-", session_id=request.session_id, model="mock",
        )

    tts_texts: list[str] = []

    async def fake_tts(text, **_):
        tts_texts.append(text)
        return b"OggS-fake", "ogg", "mock-tts"

    with patch("backend.api.routes_live_call.transcribe_bytes", new=AsyncMock(side_effect=fake_stt)), \
         patch("backend.services.call_agent.process_call_with_yandex", new=AsyncMock(side_effect=fake_llm)), \
         patch("backend.api.routes_live_call.synthesize_agent_audio", new=AsyncMock(side_effect=fake_tts)), \
         patch("backend.api.routes_live_call.notify_ivan_if_needed", new=AsyncMock()) as notify:
        with client.websocket_connect("/api/v1/live_call/ws?phone=79990004321") as ws:
            events, audio = _receive_turn(ws)
            greet = next(e for e in events if e["type"] == "agent")["text"]
            check("приветствие с предупреждением об ИИ", DISCLOSURE in greet.lower(), greet)
            check("приветствие озвучено", audio == b"OggS-fake" and DISCLOSURE in tts_texts[0].lower(), tts_texts[:1])

            ws.send_bytes(_wav())
            events, audio = _receive_turn(ws)
            heard = next(e for e in events if e["type"] == "transcript")["text"]
            reply = next(e for e in events if e["type"] == "agent")
            check("фраза распознана", heard == "Сколько стоит сайт?", heard)
            check("ответ агента без повторного предупреждения", DISCLOSURE not in reply["text"].lower(), reply["text"])
            check("ответ озвучен", audio is not None)
            check("в историю ушло приветствие", seen_histories[0][0]["text"] == greet, str(seen_histories[0][:1]))

            ws.send_bytes(_wav())
            events, _ = _receive_turn(ws)
            not_heard = next(e for e in events if e["type"] == "agent")["text"]
            check("тишина → просьба повторить без LLM", "повторите" in not_heard.lower() and len(seen_histories) == 1, not_heard)

            ws.send_bytes(_wav())
            events, _ = _receive_turn(ws)
            final = next(e for e in events if e["type"] == "agent")
            ws_types = [e["type"] for e in events]
            more = ws.receive_json()
            check("перевод на человека", final.get("action") == "transfer_to_human" and more["type"] == "transfer",
                  f"{final.get('action')} {more}")
            check("Иван уведомлён", notify.await_count >= 1, str(notify.await_count))
            check("история растёт по ходу звонка", len(seen_histories[-1]) == 3, str(len(seen_histories[-1])))
            check("call_id сохранён в истории звонков", bool(final.get("call_id")), str(ws_types))

            ws.send_json({"type": "text", "text": "Спасибо"})
            events, _ = _receive_turn(ws)
            check("текстовая реплика без микрофона", any(e["type"] == "transcript" and e["text"] == "Спасибо" for e in events))
            ws.send_json({"type": "hangup"})
            ended = ws.receive_json()
            check("завершение звонка", ended["type"] == "ended" and ended["turns"] == 3, str(ended))

    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL LIVE CALL CHECKS OK")


if __name__ == "__main__":
    main()
