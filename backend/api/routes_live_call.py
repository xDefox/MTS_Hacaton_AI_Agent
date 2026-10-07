"""Живой звонок в браузере: микрофон → WebSocket → STT → агент → TTS → динамик.

Браузер сам режет речь на фразы (VAD) и шлёт каждую как WAV 16 кГц.
Сервер держит историю диалога сессии и отвечает голосом. Конвейер тот же,
что у /process_call_voice: правила, шаблоны линии, история, уведомления Ивану.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

from backend.config import get_settings
from backend.database import SessionLocal
from backend.schemas import ActionRequired, CallRequest
from backend.services import service_settings as svc_settings
from backend.services.call_agent import process_incoming_call
from backend.services.call_history import save_call_log
from backend.services.content_filter import clean_template
from backend.services.speech_providers import SpeechError, synthesize_agent_audio, transcribe_bytes
from backend.services.telegram_notify import normalize_phone, notify_ivan_if_needed
from backend.services.yandex_llm import AI_DISCLOSURE_PREFIX, _strip_leading_disclosures

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live-call"])

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
PAGE_PATH = STATIC_DIR / "live_call.html"
VAD_PATH = STATIC_DIR / "live_vad.js"
DEFAULT_GREETING = "Здравствуйте! Компания Ивана Петрова, слушаю вас."
NOT_HEARD_REPLY = "Простите, не расслышал. Повторите, пожалуйста."
HISTORY_LIMIT = 12
# В живом разговоре паузу дольше пары секунд не ждём: лучше локальный голос, чем тишина
YANDEX_TTS_TIMEOUT_S = 6.0
SPOKEN_MAX_CHARS = 900
_GREETING_AUDIO_CACHE_LIMIT = 32
_greeting_audio: dict[str, tuple[bytes, str, str]] = {}


@router.get("/call", response_class=HTMLResponse, include_in_schema=False)
def live_call_page() -> HTMLResponse:
    return HTMLResponse(PAGE_PATH.read_text(encoding="utf-8"))


@router.get("/call/live_vad.js", include_in_schema=False)
def live_call_vad() -> Response:
    return Response(VAD_PATH.read_text(encoding="utf-8"), media_type="application/javascript")


def _greeting_for_line(line_phone: str) -> str:
    """Предупреждение об ИИ звучит один раз — в приветствии, дальше агент его не повторяет."""
    greet = ""
    if line_phone:
        prefs = svc_settings.get_settings(line_phone)
        if prefs.get("scenarios", True):
            greet = clean_template(str(prefs.get("template_greeting") or ""))
    body = greet or DEFAULT_GREETING
    if "искусственным интеллектом" in body.lower():
        return body
    return f"{AI_DISCLOSURE_PREFIX}{body}"


def _spoken_reply(text: str) -> str:
    """Голосом — весь ответ, как на экране; режем только очень длинный и по границе фразы."""
    spoken = _strip_leading_disclosures(text).strip() or text.strip()
    if len(spoken) <= SPOKEN_MAX_CHARS:
        return spoken
    head = spoken[:SPOKEN_MAX_CHARS]
    end = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
    return head[: end + 1] if end > 0 else head.rsplit(" ", 1)[0] + "."


async def _say(
    ws: WebSocket, text: str, *, spoken: str | None = None, cache: bool = False, **extra
) -> None:
    """Текст реплики агента + её голос отдельным бинарным сообщением."""
    await ws.send_json({"type": "agent", "text": text, **extra})
    phrase = spoken or text
    voiced = _greeting_audio.get(phrase) if cache else None
    if voiced is None:
        try:
            voiced = await synthesize_agent_audio(phrase, yandex_timeout=YANDEX_TTS_TIMEOUT_S)
        except SpeechError as exc:
            logger.warning("Live call TTS failed: %s", exc)
            await ws.send_json({"type": "audio_unavailable"})
            return
        if cache and voiced[2] == "yandex-speechkit":
            if len(_greeting_audio) >= _GREETING_AUDIO_CACHE_LIMIT:
                _greeting_audio.pop(next(iter(_greeting_audio)))
            _greeting_audio[phrase] = voiced
    audio, ext, engine = voiced
    await ws.send_json({"type": "audio", "format": ext, "engine": engine})
    await ws.send_bytes(audio)


@router.websocket("/api/v1/live_call/ws")
async def live_call_ws(
    ws: WebSocket,
    phone: str = Query("", description="Номер линии МТС (владелец)"),
    caller: str = Query("79000000000", description="Номер звонящего (демо)"),
) -> None:
    await ws.accept()
    line_phone = normalize_phone(phone)
    session_id = f"live-{uuid4().hex[:10]}"
    greeting = _greeting_for_line(line_phone)
    history: list[dict[str, str]] = [{"role": "assistant", "text": greeting}]
    turns = 0
    logger.info("Live call start session=%s line=%s", session_id, line_phone or "—")

    try:
        await ws.send_json({"type": "session", "session_id": session_id, "line_phone": line_phone})
        # Приветствие озвучиваем целиком — вместе с предупреждением об ИИ
        await _say(ws, greeting, spoken=greeting, cache=True)

        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text"):
                data = json.loads(message["text"])
                if data.get("type") == "hangup":
                    break
                if data.get("type") != "text":
                    continue
                user_text = str(data.get("text") or "").strip()[:2000]
                stt_ms = 0
            elif message.get("bytes"):
                await ws.send_json({"type": "status", "state": "recognizing"})
                t_stt = time.perf_counter()
                try:
                    user_text, _ = await transcribe_bytes(
                        message["bytes"],
                        audio_format="lpcm",
                        sample_rate_hertz=16000,
                        filename="utterance.wav",
                    )
                except SpeechError as exc:
                    await ws.send_json({"type": "error", "message": f"Распознавание недоступно: {exc}"})
                    continue
                stt_ms = int((time.perf_counter() - t_stt) * 1000)
                user_text = (user_text or "").strip()
            else:
                continue

            await ws.send_json({"type": "transcript", "text": user_text, "stt_ms": stt_ms})
            if not user_text:
                await _say(ws, NOT_HEARD_REPLY)
                continue

            await ws.send_json({"type": "status", "state": "thinking"})
            t_llm = time.perf_counter()
            request = CallRequest(
                session_id=session_id,
                user_message=user_text,
                line_phone=line_phone,
                client_phone=caller or "unknown",
                dialog_history=history[-HISTORY_LIMIT:],
            )
            response = await process_incoming_call(request)
            llm_ms = int((time.perf_counter() - t_llm) * 1000)

            with SessionLocal() as db:
                row = save_call_log(db, request, response)
                response.call_id = row.id
            if get_settings().notify_on_critical:
                await notify_ivan_if_needed(response, caller_phone=request.client_phone)

            history.append({"role": "user", "text": user_text})
            history.append({"role": "assistant", "text": response.agent_response})
            turns += 1
            logger.info(
                "Live call turn session=%s stt_ms=%s llm_ms=%s action=%s",
                session_id,
                stt_ms,
                llm_ms,
                response.action_required.value,
            )

            await _say(
                ws,
                response.agent_response,
                spoken=_spoken_reply(response.agent_response),
                action=response.action_required.value,
                intent=response.intent.value,
                is_critical=response.is_critical,
                summary=response.summary,
                call_id=response.call_id,
                llm_ms=llm_ms,
            )
            if response.action_required == ActionRequired.transfer_to_human:
                await ws.send_json({"type": "transfer"})
    except WebSocketDisconnect:
        pass
    finally:
        logger.info("Live call end session=%s turns=%s", session_id, turns)
        try:
            await ws.send_json({"type": "ended", "turns": turns})
            await ws.close()
        except Exception:  # noqa: BLE001 — клиент уже ушёл
            pass
