"""ORM-модели таблиц базы знаний (схема — migrations/001_create_documents_and_chunks.sql)."""

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.rag.models import EMBEDDING_DIMENSION


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей."""


class DocumentRecord(Base):
    """Документ базы знаний (одна активная редакция на ключ)."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    key: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    edition_date: Mapped[date]
    chunks_count: Mapped[int] = mapped_column(server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ChunkRecord(Base):
    """Фрагмент документа с эмбеддингом.

    Столбец ``tsv`` вычисляется в БД и в ORM не отображается.
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    document_title: Mapped[str]
    article: Mapped[str | None]
    article_title: Mapped[str | None]
    part: Mapped[int]
    content: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
