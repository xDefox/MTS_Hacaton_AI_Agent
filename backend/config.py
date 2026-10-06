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

    yc_folder_id: str = ""
    yc_api_key: str = ""

    yandex_model: str = "yandexgpt"
    yandex_model_version: str = "rc"
    yandex_temperature: float = 0.3
    yandex_max_retries: int = 1

    company_name: str = "IT-компания Ивана Петрова"
    owner_name: str = "Иван Петров"

    tg_bot_token: str = ""
    tg_chat_id: str = ""

    # SpeechKit TTS voice for agent replies (demo)
    tts_voice: str = "alena"
    tts_lang: str = "ru-RU"

    # Local SQLite for call history (ТЗ: контроль). Not for production PDn.
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
