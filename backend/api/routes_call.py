import logging
import time
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import (
    ActionRequired,
    CallCorrectionIn,
    CallHistoryItem,
    CallHistoryList,
    CallStats,
    CallRequest,
    CallResponse,
    HotlineRequest,
    Intent,
    Priority,
    RoutingRuleIn,
    ScenarioIn,
    SynthesizeRequest,
    SynthesizeResponse,
    TrainingExampleIn,
    TranscribeResponse,
    VoiceCallResponse,
)
from backend.services import service_settings as svc_settings
from backend.services.analytics import build_call_stats
from backend.services.call_agent import process_incoming_call
from backend.services.call_history import (
    call_log_to_item,
    get_call_log,
    list_call_logs,
    save_call_log,
    summarize_call_logs,
    update_call_log,
)
from backend.services.routing_rules import delete_rule, list_rules, upsert_rule
from backend.services.scenarios import delete_scenario, list_scenarios, upsert_scenario
from backend.services.speech_providers import SpeechError, synthesize_agent_audio, transcribe_bytes
from backend.services.speechkit_stt import guess_audio_format
from backend.services.telegram_notify import (
    activate_line,
    add_subscriber,
    deactivate_line,
    last_pending_phone,
    line_status,
    list_notifications,
    notify_ivan_if_needed,
    register_line,
)
from backend.services.training_examples import (
    delete_example,
    list_examples,
    upsert_example,
)
from backend.services.tts_storage import (
    audio_url_for_call,
    ensure_tts_dir,
    find_call_audio,
    save_call_audio,
)
from backend.services.yandex_llm import _strip_leading_disclosures, ensure_ai_disclosure
from backend.config import get_settings
from backend.services.warmup import warmup_demo_stack
from backend.services.greeting_audio import greeting_audio_url
from backend.services.access_audit import list_access_audit, log_access

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
    """Фронт: отключить услугу."""
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


def _text_for_tts(agent_response: str) -> str:
    """Без длинного disclosure — иначе pyttsx3 минутами «думает»."""
    settings = get_settings()
    limit = max(60, int(getattr(settings, "tts_max_chars", 220)))
    spoken = _strip_leading_disclosures(agent_response).strip()
    if not spoken:
        spoken = "Здравствуйте! Чем могу помочь?"
    # Берём первое–второе предложение — быстрее озвучка
    parts = [p.strip() for p in spoken.replace("!", ".").replace("?", ".").split(".") if p.strip()]
    if parts:
        spoken = ". ".join(parts[:2]) + "."
    if len(spoken) <= limit:
        return spoken
    cut = spoken[:limit].rsplit(" ", 1)[0].strip()
    return (cut or spoken[:limit]).rstrip(".,;") + "."


async def _attach_agent_tts(response: CallResponse) -> CallResponse:
    """Озвучить agent_response → data/tts/ + audio_url (демо)."""
    if response.call_id is None or not response.agent_response.strip():
        return response
    try:
        audio, ext, engine = await synthesize_agent_audio(_text_for_tts(response.agent_response))
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
        if get_settings().notify_on_critical:
            await notify_ivan_if_needed(response, caller_phone=data.client_phone)
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
            filename=audio.filename,
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


@router.post("/warmup")
async def warmup_stack() -> dict:
    """Прогреть Whisper + Ollama перед демо (иначе первый голосовой запрос очень долгий)."""
    return await warmup_demo_stack(get_settings())


@router.get("/greeting")
def get_greeting_meta() -> dict:
    """URL заранее озвученного приветствия (играть, пока идёт process_call_voice)."""
    url = greeting_audio_url()
    return {
        "audio_url": url,
        "ready": bool(url),
        "hint": "Фронт: play(audio_url) → параллельно POST /process_call_voice",
    }


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
    with_audio: bool = Form(
        False,
        description="Озвучка ответа (pyttsx3 медленная). Для демо лучше false + отдельно /synthesize",
    ),
    db: Session = Depends(get_db),
) -> VoiceCallResponse:
    """Голос → Whisper STT → локальный LLM → (опц.) TTS → история."""
    t_total = time.perf_counter()
    raw = await audio.read()
    fmt = audio_format or guess_audio_format(audio.filename, audio.content_type)
    t_stt = time.perf_counter()
    try:
        transcript, stt_engine = await transcribe_bytes(
            raw,
            lang=lang,
            audio_format=fmt,
            sample_rate_hertz=sample_rate_hertz,
            filename=audio.filename,
        )
    except SpeechError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    stt_ms = int((time.perf_counter() - t_stt) * 1000)

    user_text = (transcript or "").strip()
    if not user_text:
        user_text = (
            "На линии только шум или тишина, разборчивой речи не слышно. "
            "Попроси перефразировать и назвать цель звонка."
        )

    data = CallRequest(
        session_id=session_id,
        user_message=user_text,
        client_phone=client_phone or "unknown",
    )
    t_llm = time.perf_counter()
    try:
        response = await process_incoming_call(data)
        llm_ms = int((time.perf_counter() - t_llm) * 1000)
        row = save_call_log(db, data, response)
        response.call_id = row.id
        if get_settings().notify_on_critical:
            await notify_ivan_if_needed(response, caller_phone=data.client_phone)
        if with_audio:
            response = await _attach_agent_tts(response)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    total_ms = int((time.perf_counter() - t_total) * 1000)
    latency = {"stt": stt_ms, "llm": llm_ms, "total": total_ms}
    logger.info(
        "Voice latency session=%s stt_ms=%s llm_ms=%s total_ms=%s model=%s",
        session_id,
        stt_ms,
        llm_ms,
        total_ms,
        response.model,
    )

    return VoiceCallResponse(
        **response.model_dump(),
        transcript=transcript,
        stt_engine=stt_engine,
        greeting_audio_url=greeting_audio_url(),
        latency_ms=latency,
    )


@router.get("/calls", response_model=CallHistoryList)
def get_calls(
    critical_only: bool = Query(False, description="Только важные (is_critical)"),
    session_id: Optional[str] = Query(None, description="Фильтр по сессии звонка"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> CallHistoryList:
    rows = list_call_logs(
        db,
        critical_only=critical_only,
        session_id=session_id,
        limit=limit,
    )
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
    log_access("view_call", call_id=call_id)
    return call_log_to_item(row)


@router.patch("/calls/{call_id}", response_model=CallHistoryItem)
def patch_call(
    call_id: int,
    body: CallCorrectionIn,
    db: Session = Depends(get_db),
) -> CallHistoryItem:
    """Ручная корректировка расшифровки / ответа ИИ / резюме (CJM)."""
    row = update_call_log(db, call_id, body.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    log_access("correct_call", call_id=call_id, detail="manual_patch")
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
    log_access("listen_audio", call_id=call_id, detail=path.name)
    media = "audio/wav" if path.suffix.lower() == ".wav" else "audio/ogg"
    return FileResponse(path, media_type=media, filename=path.name)


@router.get("/stats")
def get_stats(
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict:
    """Аналитика по звонкам (ТЗ: усиление ценности)."""
    return build_call_stats(db, limit=limit)


@router.get("/routing_rules")
def get_routing_rules() -> dict:
    """Правила маршрутизации (ТЗ: контроль)."""
    return {"items": list_rules(), "total": len(list_rules())}


@router.put("/routing_rules")
def put_routing_rule(body: RoutingRuleIn) -> dict:
    return upsert_rule(body.model_dump())


@router.delete("/routing_rules/{rule_id}")
def remove_routing_rule(rule_id: str) -> dict:
    ok = delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return {"deleted": True, "id": rule_id}


@router.get("/scenarios")
def get_scenarios() -> dict:
    """Сценарии приветствия / FAQ (ТЗ: редактирование сценариев)."""
    return {"items": list_scenarios(), "total": len(list_scenarios())}


@router.put("/scenarios")
def put_scenario(body: ScenarioIn) -> dict:
    return upsert_scenario(body.model_dump())


@router.delete("/scenarios/{scenario_id}")
def remove_scenario(scenario_id: str) -> dict:
    ok = delete_scenario(scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return {"deleted": True, "id": scenario_id}


@router.post("/hotline", response_model=CallResponse)
async def hotline_transfer(
    body: HotlineRequest,
    db: Session = Depends(get_db),
) -> CallResponse:
    """
    Горячая линия: принудительный перевод на человека (ТЗ: экстренный перевод).
    Без LLM — мгновенно для демо.
    """
    settings = get_settings()
    text = ensure_ai_disclosure(
        "Соединяю вас с Иваном. Пожалуйста, оставайтесь на линии."
    )
    response = CallResponse(
        agent_response=text,
        is_critical=True,
        priority=Priority.critical,
        intent=Intent.escalation,
        action_required=ActionRequired.transfer_to_human,
        summary=(
            f"Горячая линия: звонящий запросил человека. "
            f"Тел: {body.client_phone or 'unknown'}. Текст: {body.user_message[:200]}"
        ),
        caller_name=None,
        recommended_next_step="Принять звонок / перезвонить немедленно",
        session_id=body.session_id,
        model="hotline-rule",
    )
    data = CallRequest(
        session_id=body.session_id,
        user_message=body.user_message,
        client_phone=body.client_phone or "unknown",
    )
    row = save_call_log(db, data, response)
    response.call_id = row.id
    if settings.notify_on_critical:
        await notify_ivan_if_needed(response, caller_phone=body.client_phone)
    return response


@router.get("/notifications")
def get_notifications(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Лента уведомлений Ивану (CJM: Telegram/кабинет)."""
    items = list_notifications(limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/audit")
def get_audit(limit: int = Query(100, ge=1, le=500)) -> dict:
    """Журнал доступа к карточкам/аудио (комплаенс: right to review)."""
    items = list_access_audit(limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/training_examples")
def get_training_examples() -> dict:
    """Примеры обучения агента (ТЗ усиление)."""
    items = list_examples()
    return {"items": items, "total": len(items)}


@router.put("/training_examples")
def put_training_example(body: TrainingExampleIn) -> dict:
    return upsert_example(body.model_dump())


@router.delete("/training_examples/{example_id}")
def remove_training_example(example_id: str) -> dict:
    ok = delete_example(example_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Example {example_id} not found")
    return {"deleted": True, "id": example_id}

