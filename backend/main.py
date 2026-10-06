import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_call import router as call_router
from backend.config import get_settings
from backend.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="MTS AI Agent API",
    description=(
        "Трек 1: ИИ-агент входящих звонков для Ивана. "
        "YandexGPT + резюме; SQLite-история для контроля (ТЗ)."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(call_router)


@app.get("/health")
def health_check():
    settings = get_settings()
    db_hint = settings.database_url.split("///")[-1] if "///" in settings.database_url else "configured"
    return {
        "status": "ok",
        "message": "API is running",
        "yandex_configured": bool(settings.yc_folder_id and settings.yc_api_key),
        "model": f"{settings.yandex_model}:{settings.yandex_model_version}",
        "database": db_hint,
    }
