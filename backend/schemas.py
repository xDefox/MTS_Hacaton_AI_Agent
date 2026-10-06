from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ActionRequired(str, Enum):
    """What the backend / UI should do next (ТЗ: голос, чат, человек)."""

    continue_dialog = "continue_dialog"
    transfer_to_human = "transfer_to_human"
    offer_telegram_chat = "offer_telegram_chat"
    callback_recommended = "callback_recommended"


class Intent(str, Enum):
    commercial = "commercial"
    support_request = "support_request"
    complaint = "complaint"
    faq = "faq"
    partnership = "partnership"
    spam = "spam"
    wrong_number = "wrong_number"
    escalation = "escalation"
    other = "other"


class Priority(str, Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class CallRequest(BaseModel, extra="allow"):
    """Incoming turn from frontend / telephony (STT text)."""

    session_id: str = Field(..., description="Call / dialog session id")
    user_message: str = Field(..., min_length=1, max_length=4000, description="Caller utterance (or STT transcript)")
    client_phone: Optional[str] = Field(default="unknown", description="Caller phone if known")
    dialog_history: Optional[list[dict[str, str]]] = Field(
        default=None,
        description='Optional prior turns: [{"role":"user"|"assistant","text":"..."}]',
    )


class AgentLLMOutput(BaseModel):
    """
    Strict JSON shape for YandexGPT structured output.

    Yandex requires EVERY field to be required (no optional properties).
    Use empty string for unknown caller_name.
    """

    agent_response: str = Field(
        ...,
        description="What the voice agent says to the caller (1–3 short sentences, Russian)",
    )
    is_critical: bool = Field(
        ...,
        description="True if Ivan must be notified urgently / should call back",
    )
    priority: Priority = Field(..., description="critical | high | normal | low")
    intent: Intent = Field(..., description="Request category")
    action_required: ActionRequired = Field(..., description="Next routing action")
    summary: str = Field(
        ...,
        description="2–4 sentences for Ivan in Telegram: who called, about what, what to do",
    )
    caller_name: str = Field(
        ...,
        description="Caller name if introduced, otherwise empty string",
    )
    recommended_next_step: str = Field(..., description="Short next step for Ivan")


class CallResponse(BaseModel):
    """API response for frontend / Telegram / demo UI."""

    agent_response: str
    is_critical: bool
    priority: Priority
    intent: Intent
    action_required: ActionRequired
    summary: str
    caller_name: Optional[str] = None
    recommended_next_step: str
    session_id: str
    model: str = "yandexgpt"
    call_id: Optional[int] = Field(
        default=None,
        description="ID записи в истории звонков (SQLite)",
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="URL озвучки agent_response (демо TTS → data/tts/). В проде — стрим в трубку.",
    )
    tts_engine: Optional[str] = Field(
        default=None,
        description="Движок озвучки, если with_audio=true",
    )


class SynthesizeRequest(BaseModel):
    """Текст → речь (SpeechKit TTS)."""

    text: str = Field(..., min_length=1, max_length=5000)
    voice: Optional[str] = Field(default=None, description="Голос SpeechKit, по умолчанию из настроек")
    lang: str = "ru-RU"


class SynthesizeResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None
    filename: str
    engine: str = "pyttsx3-local"
    note: str = (
        "Демо: файл в data/tts/. Локальный TTS по умолчанию; в проде — стрим в трубку."
    )


class CallHistoryItem(BaseModel):
    """Карточка звонка для дашборда Ивана (ТЗ: контроль / история)."""

    id: int
    session_id: str
    caller_phone: str
    user_message: str
    agent_response: str
    summary: str
    is_critical: bool
    priority: str
    intent: str
    action_required: str
    caller_name: Optional[str] = None
    recommended_next_step: str
    model: str
    created_at: datetime


class CallHistoryList(BaseModel):
    items: list[CallHistoryItem]
    total: int


class TranscribeResponse(BaseModel):
    """Результат STT (локальный Whisper по умолчанию)."""

    transcript: str
    lang: str = "ru-RU"
    audio_format: str = "oggopus"
    engine: str = "faster-whisper"


class VoiceCallResponse(CallResponse):
    """Голос → STT → агент + история."""

    transcript: str = Field(..., description="Распознанный текст")
    stt_engine: str = "faster-whisper"


class RoutingRuleIn(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    is_critical: Optional[bool] = None
    intent: Optional[str] = None
    action_required: Optional[str] = None
    enabled: bool = True


class ScenarioIn(BaseModel):
    id: Optional[str] = None
    name: str
    kind: str = "custom"  # greeting | faq | custom
    text: str
    enabled: bool = True


class HotlineRequest(BaseModel):
    """Экстренный перевод на человека (ТЗ: усиление / горячая линия)."""

    session_id: str
    user_message: str = Field(
        default="Просьба соединить с человеком",
        min_length=1,
    )
    client_phone: Optional[str] = "unknown"


class CallCorrectionIn(BaseModel):
    """Ручная правка расшифровки / ответа / резюме (CJM: корректировка ответов ИИ)."""

    user_message: Optional[str] = None
    agent_response: Optional[str] = None
    summary: Optional[str] = None
    is_critical: Optional[bool] = None
    priority: Optional[str] = None
    intent: Optional[str] = None
    action_required: Optional[str] = None
    caller_name: Optional[str] = None
    recommended_next_step: Optional[str] = None


class TrainingExampleIn(BaseModel):
    """Пример для обучения агента (ТЗ усиление)."""

    id: Optional[str] = None
    user_message: str
    expected_intent: str = "other"
    expected_action: str = "continue_dialog"
    note: str = ""
    enabled: bool = True

