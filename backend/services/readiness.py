"""Чеклист готовности (ТЗ: простота подключения ≤ 5 минут)."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select

from backend.config import Settings, get_settings
from backend.database import SessionLocal, init_db
from backend.models import CallLog
from backend.services.routing_rules import load_rules
from backend.services.scenarios import load_scenarios
from backend.services.training_examples import load_examples


async def check_ollama(settings: Settings) -> dict[str, Any]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
        if resp.status_code >= 400:
            return {"ok": False, "detail": f"HTTP {resp.status_code}"}
        models = [m.get("name", "") for m in (resp.json().get("models") or [])]
        wanted = settings.ollama_model
        has_model = any(wanted in name for name in models)
        return {
            "ok": True,
            "reachable": True,
            "has_model": has_model,
            "models_sample": models[:5],
            "wanted": wanted,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reachable": False, "detail": str(exc)[:200]}


def check_database() -> dict[str, Any]:
    try:
        init_db()
        with SessionLocal() as db:
            db.execute(select(CallLog.id).limit(1))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)[:200]}


def build_readiness(settings: Settings | None = None, *, ollama: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    rules = load_rules()
    scenarios = load_scenarios()
    examples = load_examples()
    db = check_database()
    checks = {
        "database": db,
        "routing_rules": {"ok": len(rules) >= 1, "count": len(rules)},
        "scenarios": {"ok": len(scenarios) >= 1, "count": len(scenarios)},
        "training_examples": {"ok": len(examples) >= 1, "count": len(examples)},
        "providers": {
            "ok": True,
            "llm": settings.llm_provider,
            "stt": settings.stt_provider,
            "tts": settings.tts_provider,
        },
        "local_defaults": {
            "ok": (
                (settings.llm_provider or "").lower() == "local"
                and (settings.stt_provider or "").lower() == "local"
                and (settings.tts_provider or "").lower() == "local"
            ),
            "detail": "На демо жюри — local LLM/STT/TTS",
        },
    }
    if ollama is not None:
        checks["ollama"] = ollama

    required = ["database", "routing_rules", "scenarios", "providers", "local_defaults"]
    ready_core = all(checks[k].get("ok") for k in required)
    ollama_ok = bool((ollama or {}).get("ok") and (ollama or {}).get("has_model"))
    return {
        "ready": ready_core,
        "demo_ready": ready_core and ollama_ok,
        "track": 1,
        "message": (
            "Ядро готово. Для полного демо дождитесь ollama pull qwen2.5:3b"
            if ready_core and not ollama_ok
            else ("Готово к демо" if ready_core and ollama_ok else "Есть незакрытые пункты чеклиста")
        ),
        "checks": checks,
        "setup_hint": [
            "1. pip install -r requirements.txt",
            "2. ollama pull qwen2.5:3b && ollama serve",
            "3. uvicorn backend.main:app --reload --port 8000",
            "4. GET /ready → demo_ready=true",
        ],
    }
