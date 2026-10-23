from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.rag.indexer import DocumentMeta, index_document
from app.rag.models import Chunk
from app.rag.retriever import VectorRetriever
from tests.fakes import FakeEmbedder, one_hot

pytestmark = pytest.mark.anyio

TITLE = "Закон РФ «О защите прав потребителей»"


def _vector_for(text: str) -> list[float]:
    # Вопрос «вернуть товар» ближе всего к ст. 25, чуть дальше — к ст. 18, ст. 15 — ортогональна.
    if "вернуть товар" in text:
        vector = one_hot(0)
        vector[1] = 0.5
        return vector
    if "Статья 25" in text:
        return one_hot(0)
    if "Статья 18" in text:
        return one_hot(1)
    return one_hot(2)


def _chunk(article: str, title: str) -> Chunk:
    return Chunk(document_title=TITLE, article=article, article_title=title, content="Текст.")


@pytest.mark.parametrize(("question", "top_k"), [("  ", 5), ("Вопрос", 0)])
async def test_invalid_arguments_raise(question: str, top_k: int) -> None:
    lazy = async_sessionmaker(create_async_engine("postgresql+asyncpg://u:p@localhost/none"))

    with pytest.raises(ValueError):
        await VectorRetriever(lazy, FakeEmbedder()).retrieve(question, top_k=top_k)


async def test_returns_chunks_ordered_by_similarity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    embedder = FakeEmbedder(_vector_for)
    chunks = [
        _chunk("15", "Компенсация морального вреда"),
        _chunk("18", "Права потребителя при обнаружении в товаре недостатков"),
        _chunk("25", "Право потребителя на обмен товара надлежащего качества"),
    ]
    meta = DocumentMeta(key="zozpp", title=TITLE, edition_date=date(2025, 12, 28))
    await index_document(session_factory, embedder, meta, chunks, batch_size=16)

    found = await VectorRetriever(session_factory, embedder).retrieve("Как вернуть товар?", 2)

    assert [chunk.article for chunk in found] == ["25", "18"]
    assert found[0].score == pytest.approx(0.8944, abs=1e-4)  # cos между (1, 0.5) и (1, 0)
    assert found[0].article_title == "Право потребителя на обмен товара надлежащего качества"
