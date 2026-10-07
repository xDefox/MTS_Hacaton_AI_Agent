#!/usr/bin/env python3
"""Перебивание агента в живом звонке.

1) Детектор речи браузера (backend/static/live_vad.js) — через Node: эхо, кашель, гул, перебивание.
2) Сервер: фраза/текст/сброс звонка, пришедшие, пока агент ещё говорит, не ломают диалог.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.schemas import ActionRequired, CallResponse, Intent, Priority  # noqa: E402
from tests.test_live_call import _receive_turn, _wav  # noqa: E402

failed = 0


def check(name: str, ok: bool, detail: object = "") -> None:
    global failed
    if ok:
        print(f"OK   {name}")
    else:
        failed += 1
        print(f"FAIL {name}: {detail}")


def run_vad_checks() -> None:
    print("=== детектор речи в браузере (Node) ===")
    node = shutil.which("node")
    if not node:
        print("SKIP node не установлен — браузерную часть проверить нечем (https://nodejs.org)")
        return
    proc = subprocess.run(
        [node, str(ROOT / "tests" / "barge_in_check.js")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    print(proc.stdout.rstrip())
    if proc.stderr.strip():
        print(proc.stderr.rstrip())
    check("все проверки детектора", proc.returncode == 0, f"exit={proc.returncode}")


def _reply(request, settings=None) -> CallResponse:
    text = request.user_message.lower()
    if "стоп" in text or "подождите" in text:
        answer = "Конечно, слушаю вас."
    elif "цена" in text or "стоит" in text:
        answer = "Сайт-визитка стоит от 40 000 рублей. Интернет-магазин — от 120 000. Сроки от двух недель."
    else:
        answer = "Понял вас."
    return CallResponse(
        agent_response=answer,
        is_critical=False,
        priority=Priority.normal,
        intent=Intent.faq,
        action_required=ActionRequired.continue_dialog,
        summary="s",
        recommended_next_step="-",
        session_id=request.session_id,
        model="mock",
    )


def run_server_checks() -> None:
    print("\n=== сервер: перебивание во время озвучки ===")
    client = TestClient(app)
    js = client.get("/call/live_vad.js")
    check("детектор отдаётся браузеру", js.status_code == 200 and "createVad" in js.text, js.status_code)
    check("детектор отдаётся как JavaScript", "javascript" in js.headers.get("content-type", ""), js.headers.get("content-type"))
    check("страница подключает детектор", 'src="/call/live_vad.js"' in client.get("/call").text)

    transcripts = iter(["Какая цена сайта?", "Стоп, подождите"])

    async def fake_stt(audio, **kwargs):
        return next(transcripts), "mock-stt"

    histories: list[list[dict]] = []

    async def fake_llm(request, settings=None):
        histories.append(list(request.dialog_history or []))
        return _reply(request)

    async def fake_tts(text, **_):
        return b"OggS-fake", "ogg", "mock-tts"

    with patch("backend.api.routes_live_call.transcribe_bytes", new=AsyncMock(side_effect=fake_stt)), \
         patch("backend.services.call_agent.process_call_with_yandex", new=AsyncMock(side_effect=fake_llm)), \
         patch("backend.api.routes_live_call.synthesize_agent_audio", new=AsyncMock(side_effect=fake_tts)), \
         patch("backend.api.routes_live_call.notify_ivan_if_needed", new=AsyncMock()):
        with client.websocket_connect("/api/v1/live_call/ws?phone=79990004321") as ws:
            _receive_turn(ws)  # приветствие

            # Вопрос и сразу перебивание: вторая фраза уходит, пока агент ещё отвечает на первую
            ws.send_bytes(_wav())
            ws.send_bytes(_wav())
            first, first_audio = _receive_turn(ws)
            second, second_audio = _receive_turn(ws)
            first_reply = next(e for e in first if e["type"] == "agent")["text"]
            second_heard = next(e for e in second if e["type"] == "transcript")["text"]
            second_reply = next(e for e in second if e["type"] == "agent")["text"]
            check("ответ на вопрос дошёл", "40 000" in first_reply and first_audio is not None, first_reply)
            check("перебивающая фраза распознана", second_heard == "Стоп, подождите", second_heard)
            check("агент реагирует на перебивание", second_reply == "Конечно, слушаю вас.", second_reply)
            check("перебивание озвучено", second_audio is not None)
            check(
                "в истории порядок верный: вопрос → ответ → перебивание",
                [t["text"] for t in histories[1][-2:]] == ["Какая цена сайта?", first_reply],
                histories[1][-2:],
            )

            # Текстом поверх агента: тоже без потерь
            ws.send_json({"type": "text", "text": "А сроки?"})
            ws.send_json({"type": "text", "text": "Спасибо"})
            t1, _ = _receive_turn(ws)
            t2, _ = _receive_turn(ws)
            heard = [next(e for e in t if e["type"] == "transcript")["text"] for t in (t1, t2)]
            check("две текстовые реплики подряд — обе обработаны по порядку", heard == ["А сроки?", "Спасибо"], heard)

            # Сброс звонка, пока агент ещё «говорит» — звонок закрывается чисто
            ws.send_json({"type": "text", "text": "Ещё вопрос"})
            ws.send_json({"type": "hangup"})
            _receive_turn(ws)
            ended = ws.receive_json()
            check("сброс во время ответа → звонок завершён", ended.get("type") == "ended" and ended.get("turns") == 5, ended)

    print("\n=== сервер: TTS упал во время звонка ===")

    async def broken_tts(text, **_):
        from backend.services.speech_providers import SpeechError

        raise SpeechError("tts down")

    transcripts = iter(["Алло"])
    with patch("backend.api.routes_live_call.transcribe_bytes", new=AsyncMock(side_effect=fake_stt)), \
         patch("backend.services.call_agent.process_call_with_yandex", new=AsyncMock(side_effect=fake_llm)), \
         patch("backend.api.routes_live_call.synthesize_agent_audio", new=AsyncMock(side_effect=broken_tts)), \
         patch("backend.api.routes_live_call.notify_ivan_if_needed", new=AsyncMock()):
        with client.websocket_connect("/api/v1/live_call/ws?phone=79990004321") as ws:
            greet, greet_audio = _receive_turn(ws)
            check("без голоса приветствие приходит текстом", greet_audio is None and any(e["type"] == "agent" for e in greet))
            ws.send_bytes(_wav())
            turn, audio = _receive_turn(ws)
            check("без голоса звонок продолжается текстом", audio is None and any(e["type"] == "agent" for e in turn))
            ws.send_json({"type": "hangup"})
            check("и завершается штатно", ws.receive_json().get("type") == "ended")


def main() -> None:
    run_vad_checks()
    run_server_checks()
    print()
    if failed:
        print(f"FAILED: {failed}")
        raise SystemExit(1)
    print("ALL BARGE-IN CHECKS OK")


if __name__ == "__main__":
    main()
