"""История звонков scoped по line_phone + поля input/output."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.schemas import (
    ActionRequired,
    CallRequest,
    CallResponse,
    Intent,
    Priority,
)
from backend.services.call_history import (
    call_log_to_item,
    get_call_log_for_line,
    list_call_logs,
    save_call_log,
    summarize_call_logs,
)


def _resp(session_id: str, text: str = "ответ") -> CallResponse:
    return CallResponse(
        agent_response=text,
        is_critical=False,
        priority=Priority.normal,
        intent=Intent.faq,
        action_required=ActionRequired.continue_dialog,
        summary="резюме",
        recommended_next_step="—",
        session_id=session_id,
        model="test",
    )


def test_history_scoped_by_line_and_io_fields():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    save_call_log(
        db,
        CallRequest(
            session_id="a1",
            user_message="вход А",
            line_phone="79001111111",
            client_phone="79002222222",
            direction="inbound",
        ),
        _resp("a1", "выход А"),
    )
    save_call_log(
        db,
        CallRequest(
            session_id="b1",
            user_message="вход Б",
            line_phone="79003333333",
            client_phone="79004444444",
        ),
        _resp("b1", "выход Б"),
    )

    mine = list_call_logs(db, line_phone="79001111111")
    assert len(mine) == 1
    item = call_log_to_item(mine[0])
    assert item.line_phone == "79001111111"
    assert item.input == "вход А"
    assert item.output == "выход А"
    assert item.user_message == item.input
    assert item.agent_response == item.output
    assert item.direction == "inbound"

    other = list_call_logs(db, line_phone="79003333333")
    assert len(other) == 1
    assert other[0].user_message == "вход Б"

    assert get_call_log_for_line(db, mine[0].id, "79003333333") is None
    assert get_call_log_for_line(db, mine[0].id, "79001111111") is not None

    stats = summarize_call_logs(db, line_phone="79001111111")
    assert stats.total == 1
    db.close()
