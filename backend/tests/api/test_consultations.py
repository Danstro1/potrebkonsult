from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.main import app, database
from app.llm.ollama import OllamaClient
from app.rag.retriever import ScoredChunk, VectorRetriever
from tests.fakes import FakeLLMClient


@pytest.mark.anyio
async def test_private_history(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def test_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db:
            yield db

    async def retrieve(_: VectorRetriever, question: str) -> list[ScoredChunk]:
        return [ScoredChunk(uuid4(), "Закон", "18", None, 1, "Выдержка", 0.9)]

    monkeypatch.setattr(VectorRetriever, "retrieve", retrieve)
    monkeypatch.setattr(OllamaClient, "complete", FakeLLMClient("Ответ [1]").complete)
    app.dependency_overrides[database] = test_db
    body = {"username": uuid4().hex, "password": uuid4().hex}
    other = {**body, "username": uuid4().hex}
    path = "/api/consultations"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as api:
            assert (await api.get(path)).status_code == 401
            assert (await api.post("/api/auth/register", json=body)).status_code == 201
            assert (await api.post("/api/auth/register", json=body)).status_code == 409
            assert (await api.get("/api/auth/me")).json()["username"] == body["username"]
            assert (await api.post(path, json={"question": "?"})).status_code == 422
            created = await api.post(path, json={"question": "Как подать претензию?"})
            assert created.status_code == 201
            key = path + "/" + created.json()["id"]
            assert (await api.patch(key, json={"helpful": True})).status_code == 204
            assert (await api.get(path)).json()[0]["helpful"] is True
            assert (await api.post("/api/auth/logout")).status_code == 204
            assert (await api.get(path)).status_code == 401
            assert (await api.post("/api/auth/register", json=other)).status_code == 201
            assert (await api.get(path)).json() == []
            assert (await api.delete(key)).status_code == 404
            assert (await api.patch(key, json={"helpful": False})).status_code == 404
            assert (await api.post("/api/auth/login", json=body)).status_code == 200
            assert (await api.delete(key)).status_code == 204
            assert (await api.get(path)).json() == []
    finally:
        app.dependency_overrides.pop(database)
        async with session_factory() as db:
            await db.execute(
                text("DELETE FROM accounts WHERE username IN (:first,:second)"),
                {"first": body["username"], "second": other["username"]},
            )
            await db.commit()
