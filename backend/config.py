from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "calls.db"


class Settings(BaseSettings):
    """Runtime config from environment / .env (never commit secrets)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # local = Ollama+Whisper+local TTS (default for MTS contour demo)
    # yandex = external YandexGPT/SpeechKit (legacy / optional)
    llm_provider: str = "local"
    stt_provider: str = "local"
    tts_provider: str = "local"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_temperature: float = 0.0
    ollama_timeout_sec: float = 45.0
    # Полный LLM (нет правила в тексте)
    ollama_num_ctx: int = 1024
    ollama_num_predict: int = 100
    ollama_keep_alive: str = "2h"
    # Lite: правило сработало → всё равно LLM (жюри), но крошечный промпт
    ollama_lite_on_rule: bool = True
    ollama_lite_num_ctx: int = 512
    ollama_lite_num_predict: int = 64
    # True = вообще без Ollama при правиле (НЕ для демо жюри «строго LLM»)
    ollama_rules_fast_path: bool = False

    whisper_model_size: str = "tiny"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = 8
    ollama_num_thread: int = 8

    tts_timeout_sec: float = 20.0
    tts_max_chars: int = 220

    yc_folder_id: str = ""
    yc_api_key: str = ""

    yandex_model: str = "yandexgpt"
    yandex_model_version: str = "rc"
    yandex_temperature: float = 0.3
    yandex_max_retries: int = 1

    company_name: str = "IT-компания Ивана Петрова"
    owner_name: str = "Иван Петров"

    # SpeechKit TTS voice (only if tts_provider=yandex)
    tts_voice: str = "alena"
    tts_lang: str = "ru-RU"

    # Local SQLite for call history (ТЗ: контроль). Not for production PDn.
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

    # CJM: уведомления Ивану (опционально; без токена — только data/notifications.jsonl)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # Алиасы для фронта/main (TG_BOT_TOKEN / TG_CHAT_ID)
    tg_bot_token: str = ""
    tg_chat_id: str = ""
    notify_on_critical: bool = True

    warmup_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
