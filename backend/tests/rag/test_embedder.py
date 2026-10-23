import json

import httpx
import pytest

from app.rag.embedder import EmbeddingError, OllamaEmbedder

pytestmark = pytest.mark.anyio

BASE_URL = "http://ollama.test"


def _embedder(handler: httpx.MockTransport) -> tuple[OllamaEmbedder, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=handler)
    return OllamaEmbedder(client, BASE_URL, model="bge-m3", dimension=3), client


async def test_returns_vectors_in_order_of_texts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{BASE_URL}/api/embed"
        assert json.loads(request.content) == {"model": "bge-m3", "input": ["а", "б"]}
        return httpx.Response(200, json={"embeddings": [[1, 0, 0], [0, 1, 0]]})

    embedder, client = _embedder(httpx.MockTransport(handler))
    async with client:
        assert await embedder.embed(["а", "б"]) == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


async def test_empty_input_does_not_call_ollama() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("запрос не должен отправляться")

    embedder, client = _embedder(httpx.MockTransport(handler))
    async with client:
        assert await embedder.embed([]) == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"embeddings": [[1, 0, 0]]}),
        httpx.Response(200, json={"embeddings": [[1, 0], [0, 1]]}),
        httpx.Response(200, json={"error": "model not found"}),
        httpx.Response(500, text="internal error"),
    ],
    ids=["wrong-count", "wrong-dimension", "bad-payload", "http-500"],
)
async def test_invalid_responses_raise_embedding_error(response: httpx.Response) -> None:
    embedder, client = _embedder(httpx.MockTransport(lambda request: response))
    async with client:
        with pytest.raises(EmbeddingError):
            await embedder.embed(["а", "б"])


async def test_connection_error_raises_embedding_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    embedder, client = _embedder(httpx.MockTransport(handler))
    async with client:
        with pytest.raises(EmbeddingError):
            await embedder.embed(["а"])
