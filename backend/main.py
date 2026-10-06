import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_call import router as call_router
from backend.config import get_settings
from backend.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="MTS AI Agent API",
    description=(
        "Трек 1: ИИ-агент входящих звонков для Ивана. "
        "Локальный контур: Ollama LLM + Whisper STT + local TTS + SQLite."
    ),
    version="1.8.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(call_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


from backend.services.readiness import build_readiness, check_ollama


@app.get("/health")
def health_check():
    settings = get_settings()
    db_hint = settings.database_url.split("///")[-1] if "///" in settings.database_url else "configured"
    return {
        "status": "ok",
        "message": "API is running",
        "version": app.version,
        "llm_provider": settings.llm_provider,
        "stt_provider": settings.stt_provider,
        "tts_provider": settings.tts_provider,
        "ollama_model": settings.ollama_model,
        "whisper_model": settings.whisper_model_size,
        "yandex_configured": bool(settings.yc_folder_id and settings.yc_api_key),
        "database": db_hint,
    }


@app.get("/ready")
async def readiness_check():
    """Чеклист готовности демо (ТЗ: подключение ≤ 5 минут)."""
    settings = get_settings()
    ollama = await check_ollama(settings)
    return build_readiness(settings, ollama=ollama)
