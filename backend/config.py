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
    ollama_temperature: float = 0.1
    ollama_timeout_sec: float = 90.0
    # Скорость на CPU: короткий ctx + keep model hot + rules fast-path
    ollama_num_ctx: int = 2048
    ollama_num_predict: int = 128
    ollama_keep_alive: str = "60m"
    # False по умолчанию: организаторы требуют видимый LLM на каждом звонке.
    # True — только ускорение демо (правило без Ollama); правила всё равно
    # накладываются после LLM через apply_routing_rules (ТЗ: контроль).
    ollama_rules_fast_path: bool = False

    whisper_model_size: str = "tiny"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = 4
    ollama_num_thread: int = 6

    tts_timeout_sec: float = 25.0

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
    notify_on_critical: bool = True

    warmup_on_startup: bool = True
    tts_max_chars: int = 280


@lru_cache
def get_settings() -> Settings:
    return Settings()
