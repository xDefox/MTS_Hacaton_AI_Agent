import logging
import socket

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_call import router as call_router
from backend.api.routes_live_call import router as live_call_router
from backend.config import get_settings
from backend.database import init_db

# Windows: gRPC/httpx часто берут IPv6 → connection refused к Yandex Cloud.
# Предпочитаем IPv4 для внешней интеграции.
_orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4_first(*args, **kwargs):  # type: ignore[no-untyped-def]
    res = _orig_getaddrinfo(*args, **kwargs)
    v4 = [r for r in res if r[0] == socket.AF_INET]
    return v4 + [r for r in res if r[0] != socket.AF_INET]


socket.getaddrinfo = _getaddrinfo_ipv4_first  # type: ignore[assignment]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="MTS AI Agent API",
    description=(
        "Трек 1: ИИ-агент входящих звонков для Ивана. "
        "YandexGPT + SpeechKit STT/TTS + SQLite."
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
app.include_router(live_call_router)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    settings = get_settings()
    if settings.warmup_on_startup:
        from backend.services.warmup import warmup_demo_stack

        # Не блокируем bind порта: HF скачивание Whisper может идти минуты.
        # /process_call (текст) и YandexGPT работают сразу; голос — после прогрева.
        app.state.warmup_status = {"status": "running"}

        async def _warmup_bg() -> None:
            log = logging.getLogger(__name__)
            try:
                status = await warmup_demo_stack(settings)
                app.state.warmup_status = status
                log.info("Startup warmup done: %s", status)
            except Exception as exc:  # noqa: BLE001
                app.state.warmup_status = {"status": f"fail:{exc!s}"[:160]}
                log.warning("Startup warmup failed: %s", exc)

        import asyncio

        asyncio.create_task(_warmup_bg())
    else:
        app.state.warmup_status = {"skipped": "warmup_on_startup=false"}


from backend.services.readiness import build_readiness, check_ollama


@app.get("/health")
def health_check():
    settings = get_settings()
    db_hint = settings.database_url.split("///")[-1] if "///" in settings.database_url else "configured"
    warmup = getattr(app.state, "warmup_status", None)
    return {
        "status": "ok",
        "message": "API is running",
        "warmup": warmup,
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
