"""Индексация документа: нарезка → эмбеддинги BGE-M3 → таблица chunks.

Запуск из папки backend:
    python -m app.rag.indexer --file ../data/zozpp_2025-12-28.txt --key zozpp \
        --title "Закон РФ «О защите прав потребителей»" --edition-date 2025-12-28
"""

import argparse
import asyncio
import logging
import time
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TypeVar

import httpx
from sqlalchemy import delete, func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.models import ChunkRecord, DocumentRecord
from app.db.session import create_engine, create_session_factory
from app.rag.chunking import DEFAULT_MAX_CHARS, split_law_into_articles
from app.rag.embedder import Embedder, OllamaEmbedder
from app.rag.models import Chunk

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class DocumentMeta:
    """Описание индексируемого документа.

    Attributes:
        key: Стабильный ключ документа, например ``zozpp``.
        title: Название для ссылок на источник.
        edition_date: Дата редакции текста.
    """

    key: str
    title: str
    edition_date: date


@dataclass(frozen=True, slots=True)
class IndexReport:
    """Итог индексации документа."""

    document_id: uuid.UUID
    chunks_count: int
    embedding_seconds: float
    total_seconds: float


def batched(items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    """Делит последовательность на пакеты фиксированного размера.

    Args:
        items: Исходная последовательность.
        size: Размер пакета.

    Yields:
        Пакеты длиной не больше size, последний может быть короче.

    Raises:
        ValueError: Если size не положителен.
    """
    if size <= 0:
        raise ValueError("Размер пакета должен быть положительным")
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def embed_chunks(
    chunks: Sequence[Chunk], embedder: Embedder, batch_size: int
) -> list[list[float]]:
    """Считает эмбеддинги фрагментов пакетами.

    Args:
        chunks: Фрагменты документа.
        embedder: Источник эмбеддингов.
        batch_size: Сколько фрагментов отправлять за один запрос.

    Returns:
        Векторы в порядке фрагментов.
    """
    vectors: list[list[float]] = []
    for batch in batched(chunks, batch_size):
        vectors.extend(await embedder.embed([chunk.embedding_text() for chunk in batch]))
        logger.info("index_embed_progress", extra={"done": len(vectors), "total": len(chunks)})
    return vectors


async def index_document(
    session_factory: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    meta: DocumentMeta,
    chunks: Sequence[Chunk],
    batch_size: int,
) -> IndexReport:
    """Сохраняет фрагменты документа с эмбеддингами, заменяя прежнюю редакцию.

    Эмбеддинги считаются до открытия транзакции: это самая долгая часть, и держать
    транзакцию открытой всё это время незачем. Замена фрагментов атомарна — поиск
    видит либо старую редакцию целиком, либо новую.

    Args:
        session_factory: Фабрика сессий БД.
        embedder: Источник эмбеддингов.
        meta: Описание документа.
        chunks: Фрагменты документа.
        batch_size: Размер пакета для эмбеддингов.

    Returns:
        Итог индексации.

    Raises:
        ValueError: Если фрагментов нет.
        EmbeddingError: Если не удалось получить эмбеддинги.
    """
    if not chunks:
        raise ValueError("Нет фрагментов для индексации")
    started = time.perf_counter()
    vectors = await embed_chunks(chunks, embedder, batch_size)
    embedding_seconds = time.perf_counter() - started

    async with session_factory() as session, session.begin():
        upsert = (
            insert(DocumentRecord)
            .values(key=meta.key, title=meta.title, edition_date=meta.edition_date)
            .on_conflict_do_update(
                index_elements=[DocumentRecord.key],
                set_={
                    "title": meta.title,
                    "edition_date": meta.edition_date,
                    "updated_at": func.now(),
                },
            )
            .returning(DocumentRecord.id)
        )
        document_id = (await session.execute(upsert)).scalar_one()
        await session.execute(delete(ChunkRecord).where(ChunkRecord.document_id == document_id))
        await session.execute(
            insert(ChunkRecord),
            [
                {
                    "document_id": document_id,
                    "document_title": chunk.document_title,
                    "article": chunk.article,
                    "article_title": chunk.article_title,
                    "part": chunk.part,
                    "content": chunk.content,
                    "embedding": vector,
                }
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )
        await session.execute(
            update(DocumentRecord)
            .where(DocumentRecord.id == document_id)
            .values(chunks_count=len(chunks))
        )

    report = IndexReport(
        document_id=document_id,
        chunks_count=len(chunks),
        embedding_seconds=round(embedding_seconds, 2),
        total_seconds=round(time.perf_counter() - started, 2),
    )
    logger.info(
        "index_document_done",
        extra={
            "document_key": meta.key,
            "chunks_count": report.chunks_count,
            "embedding_seconds": report.embedding_seconds,
            "total_seconds": report.total_seconds,
        },
    )
    return report


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Индексация документа базы знаний")
    parser.add_argument("--file", type=Path, required=True, help="Текст документа (UTF-8)")
    parser.add_argument("--key", required=True, help="Стабильный ключ документа, например zozpp")
    parser.add_argument("--title", required=True, help="Название документа для ссылок")
    parser.add_argument("--edition-date", type=date.fromisoformat, required=True)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    chunks = split_law_into_articles(
        args.file.read_text(encoding="utf-8"), args.title, max_chars=args.max_chars
    )
    logger.info("index_chunked", extra={"document_key": args.key, "chunks_count": len(chunks)})
    engine = create_engine(settings.database_url)
    try:
        async with httpx.AsyncClient() as client:
            embedder = OllamaEmbedder(
                client,
                settings.ollama_base_url,
                model=settings.embedding_model,
                timeout_seconds=settings.embedding_timeout_seconds,
            )
            await index_document(
                create_session_factory(engine),
                embedder,
                DocumentMeta(key=args.key, title=args.title, edition_date=args.edition_date),
                chunks,
                settings.embedding_batch_size,
            )
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> None:
    """Точка входа CLI индексатора.

    Args:
        argv: Аргументы командной строки (по умолчанию — sys.argv).
    """
    configure_logging()
    asyncio.run(_run(_parse_args(argv)))


if __name__ == "__main__":
    main()
