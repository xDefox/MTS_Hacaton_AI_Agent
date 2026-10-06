from fastapi import APIRouter, HTTPException

from backend.schemas import CallRequest, CallResponse
from backend.services.yandex_llm import process_call_with_yandex

router = APIRouter(prefix="/api/v1", tags=["calls"])


@router.post("/process_call", response_model=CallResponse)
async def process_call(data: CallRequest) -> CallResponse:
    """
    Process one caller turn: YandexGPT + system prompt → structured JSON.

    Track 1 (Ivan): professional reply, criticality, intent, routing action, Telegram summary.
    """
    try:
        return await process_call_with_yandex(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
