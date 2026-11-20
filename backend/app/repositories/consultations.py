"""Параметризованные запросы к учётным записям и личной истории."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.consultations import Answer, Consultation


async def register(db: AsyncSession, name: str, password_hash: str) -> UUID | None:
    """Атомарно резервирует имя пользователя."""
    result = await db.execute(
        text(
            "INSERT INTO accounts(username,password_hash) VALUES (:name,:hash) "
            "ON CONFLICT(username) DO NOTHING RETURNING id"
        ),
        {"name": name, "hash": password_hash},
    )
    return result.scalar_one_or_none()


async def credentials(db: AsyncSession, name: str) -> tuple[UUID, str] | None:
    """Читает данные для проверки пароля."""
    row = (
        await db.execute(
            text("SELECT id,password_hash FROM accounts WHERE username=:name"), {"name": name}
        )
    ).first()
    return (row.id, row.password_hash) if row else None


async def open_session(db: AsyncSession, owner: UUID, digest: str) -> None:
    """Сохраняет новую сессию."""
    await db.execute(
        text("INSERT INTO sessions(account_id,digest) VALUES (:owner,:digest)"),
        {"owner": owner, "digest": digest},
    )
    await db.commit()


async def session_owner(db: AsyncSession, digest: str) -> tuple[UUID, str] | None:
    """Находит пользователя действующей сессии."""
    row = (
        await db.execute(
            text(
                "SELECT a.id,a.username FROM sessions s JOIN accounts a ON a.id=s.account_id "
                "WHERE s.digest=:digest AND s.expires_at>now()"
            ),
            {"digest": digest},
        )
    ).first()
    # Освобождаем подключение до долгого запроса к локальной модели.
    await db.commit()
    return (row.id, row.username) if row else None


async def close_session(db: AsyncSession, digest: str) -> None:
    """Отзывает сессию на сервере."""
    await db.execute(text("DELETE FROM sessions WHERE digest=:digest"), {"digest": digest})
    await db.commit()


async def save(db: AsyncSession, owner: UUID, question: str, answer: Answer) -> Consultation:
    """Сохраняет ответ вместе со снимком источников."""
    result = await db.execute(
        text(
            "INSERT INTO consultations(account_id,question,answer) "
            "VALUES (:owner,:question,CAST(:answer AS jsonb)) RETURNING id"
        ),
        {"owner": owner, "question": question, "answer": answer.model_dump_json()},
    )
    item = Consultation(id=result.scalar_one(), question=question, answer=answer, helpful=None)
    await db.commit()
    return item


async def history(db: AsyncSession, owner: UUID) -> list[Consultation]:
    """Возвращает последние сто консультаций пользователя."""
    rows = await db.execute(
        text(
            "SELECT id,question,answer,helpful FROM consultations WHERE account_id=:owner "
            "ORDER BY created_at DESC LIMIT 100"
        ),
        {"owner": owner},
    )
    return [Consultation.model_validate(row) for row in rows.mappings()]


async def vote(db: AsyncSession, owner: UUID, key: UUID, helpful: bool) -> bool:
    """Обновляет оценку только у владельца консультации."""
    result = await db.execute(
        text(
            "UPDATE consultations SET helpful=:helpful "
            "WHERE id=:id AND account_id=:owner RETURNING id"
        ),
        {"id": key, "owner": owner, "helpful": helpful},
    )
    await db.commit()
    return result.scalar_one_or_none() is not None


async def remove(db: AsyncSession, owner: UUID, key: UUID) -> bool:
    """Удаляет запись личной истории."""
    result = await db.execute(
        text("DELETE FROM consultations WHERE id=:id AND account_id=:owner RETURNING id"),
        {"id": key, "owner": owner},
    )
    await db.commit()
    return result.scalar_one_or_none() is not None
