from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import CallHistoryItem, CallHistoryList, CallRequest, CallResponse
from backend.services.call_history import call_log_to_item, get_call_log, list_call_logs, save_call_log
from backend.services.yandex_llm import process_call_with_yandex

router = APIRouter(prefix="/api/v1", tags=["calls"])


@router.post("/process_call", response_model=CallResponse)
async def process_call(
    data: CallRequest,
    db: Session = Depends(get_db),
) -> CallResponse:
    """
    Process one caller turn: YandexGPT + system prompt → structured JSON,
    then persist to local SQLite history (ТЗ: контроль / история звонков).
    """
    try:
        response = await process_call_with_yandex(data)
        row = save_call_log(db, data, response)
        response.call_id = row.id
        return response
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/calls", response_model=CallHistoryList)
def get_calls(
    critical_only: bool = Query(False, description="Только важные звонки (is_critical)"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> CallHistoryList:
    """История звонков для дашборда Ивана (новые сверху)."""
    rows = list_call_logs(db, critical_only=critical_only, limit=limit)
    items = [call_log_to_item(row) for row in rows]
    return CallHistoryList(items=items, total=len(items))


@router.get("/calls/{call_id}", response_model=CallHistoryItem)
def get_call_detail(call_id: int, db: Session = Depends(get_db)) -> CallHistoryItem:
    """Детали одного звонка: резюме + реплика + ответ агента."""
    row = get_call_log(db, call_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return call_log_to_item(row)
