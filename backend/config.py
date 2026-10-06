from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Structured JSON output is supported on the release-candidate line.
    yandex_model_version: str = "rc"
    yandex_temperature: float = 0.3
    yandex_max_retries: int = 1

    company_name: str = "IT-компания Ивана Петрова"
    owner_name: str = "Иван Петров"


@lru_cache
def get_settings() -> Settings:
    return Settings()
