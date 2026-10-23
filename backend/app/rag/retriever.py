"""Векторный поиск фрагментов по вопросу пользователя."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ChunkRecord
from app.rag.embedder import Embedder


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """Найденный фрагмент с оценкой близости к вопросу.

    Attributes:
        chunk_id: Идентификатор фрагмента в таблице chunks.
        document_title: Название документа.
        article: Номер статьи (None — преамбула).
        article_title: Название статьи.
        part: Номер части статьи.
        content: Текст фрагмента.
        score: Косинусное сходство с вопросом (1 — полное совпадение).
    """

    chunk_id: uuid.UUID
    document_title: str
    article: str | None
    article_title: str | None
    part: int
    content: str
    score: float


class VectorRetriever:
    """Поиск ближайших фрагментов по косинусному расстоянию (pgvector, HNSW)."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], embedder: Embedder
    ) -> None:
        """Создаёт поисковик.

        Args:
            session_factory: Фабрика сессий БД.
            embedder: Источник эмбеддингов (та же модель, что при индексации).
        """
        self._session_factory = session_factory
        self._embedder = embedder

    async def retrieve(self, question: str, top_k: int = 5) -> list[ScoredChunk]:
        """Возвращает top_k фрагментов, ближайших к вопросу.

        Порог релевантности здесь не применяется: решение об отказе принимает
        сервис, а для оценки поиска нужны сырые результаты.

        Args:
            question: Вопрос пользователя.
            top_k: Сколько фрагментов вернуть.

        Returns:
            Фрагменты в порядке убывания сходства.

        Raises:
            ValueError: Если вопрос пустой или top_k не положителен.
            EmbeddingError: Если не удалось получить эмбеддинг вопроса.
        """
        if not question.strip():
            raise ValueError("Вопрос не должен быть пустым")
        if top_k <= 0:
            raise ValueError("top_k должен быть положительным")

        [vector] = await self._embedder.embed([question.strip()])
        # Вектор уходит параметром запроса; оператор <=> подставляет pgvector.
        distance = ChunkRecord.embedding.cosine_distance(vector).label("distance")
        stmt = select(ChunkRecord, distance).order_by(distance).limit(top_k)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()
        return [
            ScoredChunk(
                chunk_id=record.id,
                document_title=record.document_title,
                article=record.article,
                article_title=record.article_title,
                part=record.part,
                content=record.content,
                score=round(1.0 - float(row_distance), 4),
            )
            for record, row_distance in rows
        ]
