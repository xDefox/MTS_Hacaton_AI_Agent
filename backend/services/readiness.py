"""Чеклист готовности (ТЗ: простота подключения ≤ 5 минут)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.config import Settings, get_settings
from backend.database import SessionLocal, init_db
from backend.models import CallLog
from backend.services.routing_rules import load_rules
from backend.services.scenarios import load_scenarios
from backend.services.training_examples import load_examples


async def check_ollama(settings: Settings) -> dict[str, Any]:
    """Оставлено для совместимости; при llm=yandex не требуется."""
    if (settings.llm_provider or "").strip().lower() != "local":
        return {"ok": True, "skipped": True, "detail": "llm_provider!=local"}
    import httpx

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
    yandex_ok = bool(settings.yc_folder_id and settings.yc_api_key)
    llm = (settings.llm_provider or "").strip().lower()
    stt = (settings.stt_provider or "").strip().lower()
    tts = (settings.tts_provider or "").strip().lower()
    yandex_stack = llm == "yandex" and stt == "yandex" and tts == "yandex"

    checks = {
        "database": db,
        "routing_rules": {"ok": len(rules) >= 1, "count": len(rules)},
        "scenarios": {"ok": len(scenarios) >= 1, "count": len(scenarios)},
        "training_examples": {"ok": len(examples) >= 1, "count": len(examples)},
        "providers": {
            "ok": True,
            "llm": llm,
            "stt": stt,
            "tts": tts,
        },
        "yandex_credentials": {
            "ok": yandex_ok if llm == "yandex" or stt == "yandex" or tts == "yandex" else True,
            "detail": "YC_FOLDER_ID + YC_API_KEY" if yandex_ok else "missing secrets",
        },
        "yandex_stack": {
            "ok": yandex_stack,
            "detail": "LLM/STT/TTS = yandex",
        },
    }
    if ollama is not None and llm == "local":
        checks["ollama"] = ollama

    required = ["database", "routing_rules", "scenarios", "providers", "yandex_credentials"]
    ready_core = all(checks[k].get("ok") for k in required)
    demo_ready = ready_core and yandex_stack and yandex_ok
    return {
        "ready": ready_core,
        "demo_ready": demo_ready,
        "track": 1,
        "message": (
            "Готово к демо (YandexGPT + SpeechKit)"
            if demo_ready
            else ("Ядро готово, проверьте Yandex-стек" if ready_core else "Есть незакрытые пункты чеклиста")
        ),
        "checks": checks,
        "setup_hint": [
            "1. pip install -r requirements.txt",
            "2. .env: YC_FOLDER_ID, YC_API_KEY, LLM/STT/TTS=yandex",
            "3. powershell -File scripts\\start_backend.ps1",
            "4. GET /ready → demo_ready=true",
        ],
    }
