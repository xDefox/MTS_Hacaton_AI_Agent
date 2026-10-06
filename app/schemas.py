from enum import Enum
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
    user_message: str = Field(..., min_length=1, description="Caller utterance (or STT transcript)")
    client_phone: Optional[str] = Field(default="unknown", description="Caller phone if known")
    dialog_history: Optional[list[dict[str, str]]] = Field(
        default=None,
        description='Optional prior turns: [{"role":"user"|"assistant","text":"..."}]',
    )


class AgentLLMOutput(BaseModel):
    """Strict JSON shape requested from YandexGPT (structured output)."""

    agent_response: str = Field(
        ...,
        description="What the voice agent says to the caller (1–3 short sentences, Russian)",
    )
    is_critical: bool = Field(
        ...,
        description="True if Ivan must be notified urgently / should call back",
    )
    priority: Priority = Field(default=Priority.normal)
    intent: Intent = Field(default=Intent.other)
    action_required: ActionRequired = Field(default=ActionRequired.continue_dialog)
    summary: str = Field(
        ...,
        description="2–4 sentences for Ivan in Telegram: who called, about what, what to do",
    )
    caller_name: Optional[str] = Field(default=None, description="Name if the caller introduced themselves")
    recommended_next_step: str = Field(
        default="Просмотреть резюме в Telegram",
        description="Short next step for Ivan",
    )


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
