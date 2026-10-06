from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import (
    CallHistoryItem,
    CallHistoryList,
    CallRequest,
    CallResponse,
    TranscribeResponse,
    VoiceCallResponse,
)
from backend.services.call_history import call_log_to_item, get_call_log, list_call_logs, save_call_log
from backend.services.speechkit_stt import SpeechKitError, guess_audio_format, transcribe_audio
from backend.services.telegram_notify import add_subscriber, notify_call_report, payload_from_response
from backend.services.yandex_llm import process_call_with_yandex

router = APIRouter(prefix="/api/v1", tags=["calls"])


class TelegramSubscribe(BaseModel):
    chat_id: int = Field(..., description="Telegram chat_id Ивана после /start")


@router.post("/telegram/subscribe")
def telegram_subscribe(body: TelegramSubscribe) -> dict:
    """Бот регистрирует чат, куда слать отчёты по реальным звонкам."""
    add_subscriber(body.chat_id)
    return {"ok": True, "chat_id": body.chat_id}


@router.post("/process_call", response_model=CallResponse)
async def process_call(
    data: CallRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CallResponse:
    """
    Process one caller turn: YandexGPT → JSON, then save to SQLite history
    (ТЗ: контроль и управление — история звонков).
    """
    try:
        response = await process_call_with_yandex(data)
        row = save_call_log(db, data, response)
        response.call_id = row.id
        background_tasks.add_task(
            notify_call_report,
            **payload_from_response(
                response,
                phone=data.client_phone or "unknown",
            ),
        )
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
    """SpeechKit STT: голос → текст (ТЗ: точность расшифровки)."""
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


@router.post("/process_call_voice", response_model=VoiceCallResponse)
async def process_call_voice(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(..., description="Реплика звонящего (oggopus / lpcm)"),
    session_id: str = Form(...),
    client_phone: str = Form("unknown"),
    lang: str = Form("ru-RU"),
    audio_format: Optional[Literal["oggopus", "lpcm"]] = Form(None),
    sample_rate_hertz: Optional[int] = Form(None),
    db: Session = Depends(get_db),
) -> VoiceCallResponse:
    """
    Голос → SpeechKit STT → YandexGPT агент → запись в историю.
    Демо-цепочка трека 1 без отдельного микрофонного UI.
    """
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
        background_tasks.add_task(
            notify_call_report,
            **payload_from_response(
                response,
                phone=client_phone or "unknown",
                transcript=transcript,
            ),
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
    """История звонков для дашборда Ивана (новые сверху)."""
    rows = list_call_logs(db, critical_only=critical_only, limit=limit)
    items = [call_log_to_item(row) for row in rows]
    return CallHistoryList(items=items, total=len(items))


@router.get("/calls/{call_id}", response_model=CallHistoryItem)
def get_call_detail(call_id: int, db: Session = Depends(get_db)) -> CallHistoryItem:
    """Детали звонка: резюме + реплика + ответ агента."""
    row = get_call_log(db, call_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return call_log_to_item(row)
