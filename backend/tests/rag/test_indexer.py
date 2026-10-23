from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import ChunkRecord, DocumentRecord
from app.rag.indexer import DocumentMeta, batched, embed_chunks, index_document
from app.rag.models import Chunk
from tests.fakes import FakeEmbedder

TITLE = "Закон РФ «О защите прав потребителей»"


def _chunks(count: int) -> list[Chunk]:
    return [
        Chunk(
            document_title=TITLE,
            article=str(n),
            article_title=f"Статья про {n}",
            part=1,
            content=f"Текст {n}",
        )
        for n in range(1, count + 1)
    ]


def test_batched_splits_into_fixed_size_batches() -> None:
    assert [len(batch) for batch in batched(list(range(34)), 16)] == [16, 16, 2]
    assert list(batched([], 16)) == []


def test_batched_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError):
        list(batched([1, 2], 0))


@pytest.mark.anyio
async def test_embed_chunks_sends_batches_of_embedding_texts() -> None:
    embedder = FakeEmbedder()
    chunks = _chunks(5)

    vectors = await embed_chunks(chunks, embedder, batch_size=2)

    assert [len(batch) for batch in embedder.batches] == [2, 2, 1]
    assert embedder.batches[0][0] == chunks[0].embedding_text()
    assert len(vectors) == 5


@pytest.mark.anyio
async def test_index_document_rejects_empty_chunks() -> None:
    # Движок не подключается до первого запроса, а ошибка возникает раньше.
    lazy = async_sessionmaker(create_async_engine("postgresql+asyncpg://u:p@localhost/none"))
    meta = DocumentMeta(key="test", title=TITLE, edition_date=date(2025, 12, 28))

    with pytest.raises(ValueError):
        await index_document(lazy, FakeEmbedder(), meta, [], batch_size=16)


@pytest.mark.anyio
async def test_reindexing_replaces_previous_edition(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    embedder = FakeEmbedder()
    first = DocumentMeta(key="zozpp", title=TITLE, edition_date=date(2024, 1, 1))
    second = DocumentMeta(key="zozpp", title=TITLE, edition_date=date(2025, 12, 28))

    await index_document(session_factory, embedder, first, _chunks(3), batch_size=2)
    report = await index_document(session_factory, embedder, second, _chunks(2), batch_size=2)

    async with session_factory() as session:
        documents = (await session.execute(select(DocumentRecord))).scalars().all()
        chunk_count = (await session.execute(select(func.count(ChunkRecord.id)))).scalar_one()
        dims = (await session.execute(select(ChunkRecord.embedding).limit(1))).scalar_one()
    assert len(documents) == 1
    assert documents[0].id == report.document_id
    assert documents[0].edition_date == date(2025, 12, 28)
    assert documents[0].chunks_count == 2
    assert chunk_count == 2
    assert len(dims) == 1024
