"""Настройки приложения из переменных окружения и файла .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env лежит в корне репозитория: его же читает docker compose.
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Настройки backend; значения берутся из окружения, затем из .env."""

    model_config = SettingsConfigDict(env_file=_REPO_ROOT / ".env", extra="ignore")

    database_url: str = Field(description="Строка подключения SQLAlchemy (postgresql+asyncpg://…)")
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "bge-m3"
    embedding_batch_size: int = Field(default=16, ge=1, le=256)
    embedding_timeout_seconds: float = Field(default=120.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Возвращает настройки, прочитанные один раз за процесс.

    Returns:
        Настройки приложения.
    """
    return Settings()
