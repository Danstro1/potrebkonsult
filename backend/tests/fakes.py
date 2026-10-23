"""Тестовые двойники внешних зависимостей."""

from collections.abc import Callable, Sequence

from app.rag.models import EMBEDDING_DIMENSION


def one_hot(index: int, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Возвращает единичный вектор: косинусное сходство двух таких векторов — 1 или 0."""
    vector = [0.0] * dimension
    vector[index] = 1.0
    return vector


class FakeEmbedder:
    """Эмбеддер без сети: векторы задаются функцией, вызовы запоминаются."""

    def __init__(self, vector_for: Callable[[str], list[float]] | None = None) -> None:
        self._vector_for = vector_for or (lambda text: one_hot(len(text) % EMBEDDING_DIMENSION))
        self.batches: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [self._vector_for(text) for text in texts]
