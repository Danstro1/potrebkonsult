from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import create_engine, create_session_factory

REPO_ROOT = Path(__file__).resolve().parents[2]


class _TestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    test_database_url: str | None = None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Сессии к отдельной тестовой БД; без TEST_DATABASE_URL тест пропускается."""
    url = _TestSettings().test_database_url
    if not url:
        pytest.skip("TEST_DATABASE_URL не задан — интеграционный тест пропущен")
    # Таблицы очищаются целиком, поэтому подключаться разрешено только к БД *_test.
    database = make_url(url).database or ""
    assert database.endswith("_test"), f"Интеграционные тесты очищают БД, а {database!r} не *_test"

    engine = create_engine(url)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE documents CASCADE"))
    try:
        yield create_session_factory(engine)
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE documents CASCADE"))
        await engine.dispose()
