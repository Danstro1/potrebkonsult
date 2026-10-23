"""Получение эмбеддингов BGE-M3 через Ollama."""

from collections.abc import Sequence
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from app.rag.models import EMBEDDING_DIMENSION


class EmbeddingError(Exception):
    """Не удалось получить эмбеддинги."""


class Embedder(Protocol):
    """Источник эмбеддингов для списка текстов."""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Возвращает по одному вектору на каждый текст в том же порядке."""
        ...


class _EmbedResponse(BaseModel):
    embeddings: list[list[float]]


class OllamaEmbedder:
    """Эмбеддер на основе эндпоинта Ollama ``POST /api/embed``."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        model: str = "bge-m3",
        timeout_seconds: float = 120.0,
        dimension: int = EMBEDDING_DIMENSION,
    ) -> None:
        """Создаёт эмбеддер.

        Args:
            client: Общий HTTP-клиент (переиспользуется ради пула соединений).
            base_url: Адрес Ollama, например http://localhost:11434.
            model: Имя модели эмбеддингов в Ollama.
            timeout_seconds: Таймаут запроса; первый запрос загружает модель в память.
            dimension: Ожидаемая размерность вектора.
        """
        self._client = client
        self._url = base_url.rstrip("/") + "/api/embed"
        self._model = model
        self._timeout = timeout_seconds
        self._dimension = dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Возвращает эмбеддинги текстов одним запросом.

        Args:
            texts: Тексты для векторизации.

        Returns:
            Векторы в порядке текстов.

        Raises:
            EmbeddingError: Ollama недоступна, вернула ошибку или векторы не той формы.
        """
        if not texts:
            return []
        try:
            response = await self._client.post(
                self._url,
                json={"model": self._model, "input": list(texts)},
                timeout=self._timeout,
            )
            response.raise_for_status()
            vectors = _EmbedResponse.model_validate(response.json()).embeddings
        except (httpx.HTTPError, ValidationError, ValueError) as exc:
            raise EmbeddingError("Сервис эмбеддингов недоступен или вернул ошибку") from exc

        if len(vectors) != len(texts):
            raise EmbeddingError(f"Ожидалось {len(texts)} векторов, получено {len(vectors)}")
        # Вектор другой размерности несовместим с индексом vector(1024) — лучше упасть сразу.
        if any(len(vector) != self._dimension for vector in vectors):
            raise EmbeddingError(f"Размерность эмбеддинга отличается от {self._dimension}")
        return vectors
