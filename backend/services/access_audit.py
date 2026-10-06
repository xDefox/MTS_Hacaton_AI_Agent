"""Простой audit log доступа к карточкам/аудио (комплаенс: right to review lite)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.config import ROOT_DIR

AUDIT_PATH = ROOT_DIR / "data" / "access_audit.jsonl"


def log_access(action: str, *, call_id: int | None = None, detail: str = "") -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "call_id": call_id,
        "detail": detail,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
