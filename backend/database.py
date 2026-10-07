"""SQLAlchemy engine and session for local call history (SQLite)."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.removeprefix("sqlite:///")
    db_path = Path(raw_path)
    if db_path.parent and str(db_path.parent) not in {".", ""}:
        db_path.parent.mkdir(parents=True, exist_ok=True)


def _migrate_call_logs_columns() -> None:
    """Добавить line_phone / direction в уже существующую SQLite без Alembic."""
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(call_logs)")).fetchall()
        if not rows:
            return
        names = {row[1] for row in rows}
        if "line_phone" not in names:
            conn.execute(
                text("ALTER TABLE call_logs ADD COLUMN line_phone VARCHAR(64) DEFAULT ''")
            )
        if "direction" not in names:
            conn.execute(
                text("ALTER TABLE call_logs ADD COLUMN direction VARCHAR(16) DEFAULT 'inbound'")
            )


_settings = get_settings()
_ensure_sqlite_dir(_settings.database_url)

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_call_logs_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
