from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import (
    CallHistoryItem,
    CallHistoryList,
    CallRequest,
    CallResponse,
    SynthesizeRequest,
    SynthesizeResponse,
    TranscribeResponse,
    VoiceCallResponse,
)
from backend.services.call_agent import process_incoming_call
from backend.services.call_history import call_log_to_item, get_call_log, list_call_logs, save_call_log
from backend.services.speech_providers import SpeechError, synthesize_agent_audio, transcribe_bytes
from backend.services.speechkit_stt import guess_audio_format
from backend.services.tts_storage import (
    audio_url_for_call,
    ensure_tts_dir,
    find_call_audio,
    save_call_audio,
)

router = APIRouter(prefix="/api/v1", tags=["calls"])


async def _attach_agent_tts(response: CallResponse) -> CallResponse:
    """Озвучить agent_response → data/tts/ + audio_url (демо)."""
    if response.call_id is None or not response.agent_response.strip():
        return response
    try:
        audio, ext, engine = await synthesize_agent_audio(response.agent_response)
        save_call_audio(response.call_id, audio, ext=ext)
        response.audio_url = audio_url_for_call(response.call_id)
        response.tts_engine = engine
    except SpeechError:
        response.audio_url = None
        response.tts_engine = None
    return response


@router.post("/process_call", response_model=CallResponse)
async def process_call(
    data: CallRequest,
    with_audio: bool = Query(
        False,
        description="Если true — озвучить agent_response (локальный TTS → data/tts/)",
    ),
    db: Session = Depends(get_db),
) -> CallResponse:
    """
    Одна реплика звонящего → локальный LLM (Ollama) / опц. Yandex → история.
    """
    try:
        response = await process_incoming_call(data)
        row = save_call_log(db, data, response)
        response.call_id = row.id
        if with_audio:
            response = await _attach_agent_tts(response)
        return response
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(..., description="Аудио: ogg/opus или wav"),
    lang: str = Form("ru-RU"),
    audio_format: Optional[Literal["oggopus", "lpcm"]] = Form(None),
    sample_rate_hertz: Optional[int] = Form(None),
) -> TranscribeResponse:
    """STT: по умолчанию локальный Whisper (faster-whisper)."""
    raw = await audio.read()
    fmt = audio_format or guess_audio_format(audio.filename, audio.content_type)
    try:
        text, engine = await transcribe_bytes(
            raw,
            lang=lang,
            audio_format=fmt,
            sample_rate_hertz=sample_rate_hertz,
        )
    except SpeechError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TranscribeResponse(
        transcript=text,
        lang=lang,
        audio_format=fmt,
        engine=engine,
    )


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(body: SynthesizeRequest) -> SynthesizeResponse:
    """Текст → речь (локальный TTS по умолчанию)."""
    try:
        audio, ext, engine = await synthesize_agent_audio(body.text)
    except SpeechError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    ensure_tts_dir()
    name = f"synth_{uuid4().hex[:12]}.{ext}"
    path = ensure_tts_dir() / name
    path.write_bytes(audio)
    return SynthesizeResponse(
        text=body.text,
        filename=name,
        audio_url=f"/api/v1/tts/{name}",
        engine=engine,
    )


@router.get("/tts/{filename}")
def get_synth_file(filename: str) -> FileResponse:
    """Скачать демо-файл TTS из data/tts/."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not (filename.endswith(".ogg") or filename.endswith(".wav")):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = ensure_tts_dir() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found")
    media = "audio/wav" if filename.endswith(".wav") else "audio/ogg"
    return FileResponse(path, media_type=media, filename=filename)


@router.post("/process_call_voice", response_model=VoiceCallResponse)
async def process_call_voice(
    audio: UploadFile = File(..., description="Реплика звонящего"),
    session_id: str = Form(...),
    client_phone: str = Form("unknown"),
    lang: str = Form("ru-RU"),
    audio_format: Optional[Literal["oggopus", "lpcm"]] = Form(None),
    sample_rate_hertz: Optional[int] = Form(None),
    with_audio: bool = Form(True),
    db: Session = Depends(get_db),
) -> VoiceCallResponse:
    """Голос → Whisper STT → локальный LLM → (опц.) TTS → история."""
    raw = await audio.read()
    fmt = audio_format or guess_audio_format(audio.filename, audio.content_type)
    try:
        transcript, stt_engine = await transcribe_bytes(
            raw,
            lang=lang,
            audio_format=fmt,
            sample_rate_hertz=sample_rate_hertz,
        )
    except SpeechError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = CallRequest(
        session_id=session_id,
        user_message=transcript,
        client_phone=client_phone or "unknown",
    )
    try:
        response = await process_incoming_call(data)
        row = save_call_log(db, data, response)
        response.call_id = row.id
        if with_audio:
            response = await _attach_agent_tts(response)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return VoiceCallResponse(
        **response.model_dump(),
        transcript=transcript,
        stt_engine=stt_engine,
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
    path = find_call_audio(call_id)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail="Audio not generated yet. Call process_call?with_audio=true or process_call_voice.",
        )
    media = "audio/wav" if path.suffix.lower() == ".wav" else "audio/ogg"
    return FileResponse(path, media_type=media, filename=path.name)
