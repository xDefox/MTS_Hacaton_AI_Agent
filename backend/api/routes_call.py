from typing import Literal, Optional
from uuid import uuid4
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.schemas import (
    CallHistoryItem,
    CallHistoryList,
    CallStats,
    CallRequest,
    CallResponse,
    SynthesizeRequest,
    SynthesizeResponse,
    TranscribeResponse,
    VoiceCallResponse,
)
from backend.services.call_history import (
    call_log_to_item,
    get_call_log,
    list_call_logs,
    save_call_log,
    summarize_call_logs,
)
from backend.services.speechkit_stt import (
    SpeechKitError,
    guess_audio_format,
    synthesize_ogg,
    transcribe_audio,
)
from backend.services import service_settings as svc_settings
from backend.services.telegram_notify import (
    activate_line,
    add_subscriber,
    last_pending_phone,
    line_status,
    notify_call_report,
    payload_from_response,
    register_line,
    deactivate_line,
)
from backend.services.tts_storage import (
    audio_path_for_call,
    audio_url_for_call,
    ensure_tts_dir,
    save_call_audio,
)
from backend.services.yandex_llm import process_call_with_yandex

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["calls"])


class TelegramSubscribe(BaseModel):
    chat_id: int = Field(..., description="Telegram chat_id Ивана после /start")
    phone: str = Field(default="", description="Номер линии из приложения МТС / заглушки")


class TelegramRegister(BaseModel):
    phone: str = Field(..., min_length=5, description="Номер, на который подключают услугу")


class ServiceSettingsBody(BaseModel):
    phone: str = Field(..., min_length=5)
    routing: Optional[Literal["voice", "chat", "hybrid"]] = None
    history: Optional[bool] = None
    scenarios: Optional[bool] = None
    hotline: Optional[bool] = None
    notify: Optional[Literal["all", "critical"]] = None
    mode: Optional[Literal["strict", "loyal"]] = None
    template_greeting: Optional[str] = None
    template_faq: Optional[str] = None


async def _attach_agent_tts(response: CallResponse) -> CallResponse:
    """Озвучить agent_response → data/tts/call_{id}.ogg + audio_url (демо, не прод-стрим)."""
    if response.call_id is None or not response.agent_response.strip():
        return response
    settings = get_settings()
    try:
        audio = await synthesize_ogg(
            response.agent_response,
            voice=settings.tts_voice,
            lang=settings.tts_lang,
        )
        save_call_audio(response.call_id, audio)
        response.audio_url = audio_url_for_call(response.call_id)
        response.tts_engine = "yandex-speechkit"
    except SpeechKitError:
        response.audio_url = None
        response.tts_engine = None
    return response


async def _notify_ivan(response: CallResponse, *, phone: str, transcript: str | None = None) -> None:
    try:
        await notify_call_report(
            **payload_from_response(response, phone=phone, transcript=transcript),
        )
    except Exception:
        logger.exception("Telegram notify failed")


@router.post("/telegram/register")
def telegram_register(body: TelegramRegister) -> dict:
    """Фронт: заглушка номера МТС до /start в боте."""
    try:
        phone = register_line(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Укажите номер телефона") from exc
    return line_status(phone)


@router.post("/telegram/subscribe")
def telegram_subscribe(body: TelegramSubscribe) -> dict:
    """Бот /start: услуга активна на номере."""
    phone = body.phone or last_pending_phone()
    if not phone:
        raise HTTPException(status_code=400, detail="Нет номера линии")
    activate_line(phone, body.chat_id)
    add_subscriber(body.chat_id)
    return line_status(phone)


@router.post("/telegram/deactivate")
def telegram_deactivate(body: TelegramRegister) -> dict:
    """Фронт: отключить услугу — не считать номер активированным, пока снова не будет /start."""
    try:
        phone = deactivate_line(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Укажите номер телефона") from exc
    return line_status(phone)


@router.get("/telegram/status")
def telegram_status(phone: str = Query(..., min_length=5)) -> dict:
    return line_status(phone)


@router.get("/service/settings")
def get_service_settings(phone: str = Query(..., min_length=5)) -> dict:
    """Настройки услуги по номеру — источник правды для бота."""
    return svc_settings.get_settings(phone)


@router.post("/service/settings")
def post_service_settings(body: ServiceSettingsBody) -> dict:
    """Фронт пишет настройки; бот только читает (бот необязателен)."""
    try:
        return svc_settings.update_settings(
            body.phone,
            routing=body.routing,
            history=body.history,
            scenarios=body.scenarios,
            hotline=body.hotline,
            notify=body.notify,
            mode=body.mode,
            template_greeting=body.template_greeting,
            template_faq=body.template_faq,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Укажите номер телефона") from exc


@router.post("/process_call", response_model=CallResponse)
async def process_call(
    data: CallRequest,
    with_audio: bool = Query(
        False,
        description="Если true — озвучить agent_response (SpeechKit TTS → data/tts/)",
    ),
    db: Session = Depends(get_db),
) -> CallResponse:
    try:
        response = await process_call_with_yandex(data)
        row = save_call_log(db, data, response)
        response.call_id = row.id
        if with_audio:
            response = await _attach_agent_tts(response)
        await _notify_ivan(response, phone=data.client_phone or "unknown")
        return response
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(..., description="Аудио: ogg/opus (рекомендуется) или raw lpcm"),
    lang: str = Form("ru-RU"),
    audio_format: Optional[Literal["oggopus", "lpcm"]] = Form(
        None,
        description="Если не указан — угадываем по имени файла",
    ),
    sample_rate_hertz: Optional[int] = Form(
        None,
        description="Только для lpcm: 48000 / 16000 / 8000",
    ),
) -> TranscribeResponse:
    raw = await audio.read()
    fmt = audio_format or guess_audio_format(audio.filename, audio.content_type)
    try:
        text = await transcribe_audio(
            raw,
            audio_format=fmt,
            lang=lang,
            sample_rate_hertz=sample_rate_hertz,
        )
    except SpeechKitError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TranscribeResponse(transcript=text, lang=lang, audio_format=fmt)


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(body: SynthesizeRequest) -> SynthesizeResponse:
    settings = get_settings()
    voice = body.voice or settings.tts_voice
    try:
        audio = await synthesize_ogg(body.text, voice=voice, lang=body.lang)
    except SpeechKitError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    ensure_tts_dir()
    name = f"synth_{uuid4().hex[:12]}.ogg"
    path = ensure_tts_dir() / name
    path.write_bytes(audio)
    return SynthesizeResponse(
        text=body.text,
        filename=name,
        audio_url=f"/api/v1/tts/{name}",
    )


@router.get("/tts/{filename}")
def get_synth_file(filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or not filename.endswith(".ogg"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = ensure_tts_dir() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/ogg", filename=filename)


@router.post("/process_call_voice", response_model=VoiceCallResponse)
async def process_call_voice(
    audio: UploadFile = File(..., description="Реплика звонящего (oggopus / lpcm)"),
    session_id: str = Form(...),
    client_phone: str = Form("unknown"),
    lang: str = Form("ru-RU"),
    audio_format: Optional[Literal["oggopus", "lpcm"]] = Form(None),
    sample_rate_hertz: Optional[int] = Form(None),
    with_audio: bool = Form(
        True,
        description="Озвучить ответ агента (по умолчанию да — голосовая цепочка)",
    ),
    db: Session = Depends(get_db),
) -> VoiceCallResponse:
    raw = await audio.read()
    fmt = audio_format or guess_audio_format(audio.filename, audio.content_type)
    try:
        transcript = await transcribe_audio(
            raw,
            audio_format=fmt,
            lang=lang,
            sample_rate_hertz=sample_rate_hertz,
        )
    except SpeechKitError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = CallRequest(
        session_id=session_id,
        user_message=transcript,
        client_phone=client_phone or "unknown",
    )
    try:
        response = await process_call_with_yandex(data)
        row = save_call_log(db, data, response)
        response.call_id = row.id
        if with_audio:
            response = await _attach_agent_tts(response)
        await _notify_ivan(
            response,
            phone=client_phone or "unknown",
            transcript=transcript,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return VoiceCallResponse(
        **response.model_dump(),
        transcript=transcript,
    )


@router.get("/calls", response_model=CallHistoryList)
def get_calls(
    critical_only: bool = Query(False, description="Только важные (is_critical)"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> CallHistoryList:
    rows = list_call_logs(db, critical_only=critical_only, limit=limit)
    items = [call_log_to_item(row) for row in rows]
    return CallHistoryList(items=items, total=len(items))


@router.get("/calls/stats", response_model=CallStats)
def get_call_stats(
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> CallStats:
    """Дашборд: все / важные / разбивка по intent и действию."""
    return summarize_call_logs(db, limit=limit)


@router.get("/calls/{call_id}", response_model=CallHistoryItem)
def get_call_detail(call_id: int, db: Session = Depends(get_db)) -> CallHistoryItem:
    row = get_call_log(db, call_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return call_log_to_item(row)


@router.get("/calls/{call_id}/audio")
def get_call_audio(call_id: int, db: Session = Depends(get_db)) -> FileResponse:
    row = get_call_log(db, call_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    path = audio_path_for_call(call_id)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Audio not generated yet. Call process_call?with_audio=true or process_call_voice.",
        )
    return FileResponse(
        path,
        media_type="audio/ogg",
        filename=f"call_{call_id}.ogg",
    )
