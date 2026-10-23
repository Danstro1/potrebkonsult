"""Создание асинхронного подключения к PostgreSQL."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str) -> AsyncEngine:
    """Создаёт асинхронный движок SQLAlchemy.

    Args:
        database_url: Строка подключения вида postgresql+asyncpg://…

    Returns:
        Движок с проверкой соединений перед использованием.
    """
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создаёт фабрику сессий.

    Args:
        engine: Асинхронный движок.

    Returns:
        Фабрика сессий без истечения объектов после commit.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
