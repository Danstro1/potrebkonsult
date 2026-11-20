"""Точка входа локального HTTP API."""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.llm.ollama import OllamaClient
from app.rag.embedder import EmbeddingError, OllamaEmbedder
from app.rag.retriever import VectorRetriever
from app.repositories import consultations as repo
from app.schemas.consultations import Consultation, Credentials, Identity, Question, Vote
from app.services.auth import hash_password, matches, token_digest
from app.services.consultations import answer_question

settings = get_settings()
engine = create_engine(settings.database_url)
factory = create_session_factory(engine)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Освобождает подключения при остановке приложения."""
    configure_logging()
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="ПотребКонсульт", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


async def database() -> AsyncIterator[AsyncSession]:
    """Выдаёт сессию на один запрос."""
    async with factory() as db:
        yield db


Database = Annotated[AsyncSession, Depends(database)]
Ticket = Annotated[str | None, Cookie(alias="pk_session")]


async def identity(db: Database, ticket: Ticket = None) -> tuple[UUID, str]:
    """Проверяет срок и подлинность сессионного токена."""
    owner = await repo.session_owner(db, token_digest(ticket)) if ticket else None
    if owner is None:
        raise HTTPException(401, "Войдите в аккаунт")
    return owner


Owner = Annotated[tuple[UUID, str], Depends(identity)]


async def _session(db: AsyncSession, response: Response, key: UUID, name: str) -> Identity:
    token = secrets.token_urlsafe(32)
    await repo.open_session(db, key, token_digest(token))
    response.set_cookie(
        "pk_session", token, httponly=True, samesite="strict", max_age=604800, path="/api"
    )
    return Identity(username=name)


@app.post("/api/auth/register", status_code=201)
async def register(data: Credentials, db: Database, response: Response) -> Identity:
    """Регистрирует пользователя и открывает сессию."""
    name = data.username.lower()
    key = await repo.register(db, name, await run_in_threadpool(hash_password, data.password))
    if key is None:
        raise HTTPException(409, "Имя пользователя занято")
    return await _session(db, response, key, name)


@app.post("/api/auth/login")
async def login(data: Credentials, db: Database, response: Response) -> Identity:
    """Открывает сессию по паролю."""
    name = data.username.lower()
    account = await repo.credentials(db, name)
    if not account or not await run_in_threadpool(matches, data.password, account[1]):
        raise HTTPException(401, "Неверное имя или пароль")
    return await _session(db, response, account[0], name)


@app.get("/api/auth/me")
async def me(owner: Owner) -> Identity:
    """Возвращает имя владельца сессии."""
    return Identity(username=owner[1])


@app.post("/api/auth/logout", status_code=204)
async def logout(db: Database, response: Response, ticket: Ticket = None) -> None:
    """Завершает сессию."""
    if ticket:
        await repo.close_session(db, token_digest(ticket))
    response.delete_cookie("pk_session", path="/api")


@app.get("/api/consultations")
async def history(db: Database, owner: Owner) -> list[Consultation]:
    """Читает личную историю."""
    return await repo.history(db, owner[0])


@app.post("/api/consultations", status_code=201)
async def ask(data: Question, db: Database, owner: Owner) -> Consultation:
    """Ищет правовые основания и сохраняет консультацию."""
    async with httpx.AsyncClient() as client:
        retriever = VectorRetriever(
            factory,
            OllamaEmbedder(
                client,
                settings.ollama_base_url,
                settings.embedding_model,
                settings.embedding_timeout_seconds,
            ),
        )
        llm = OllamaClient(client, settings.ollama_base_url, settings.chat_model)
        try:
            chunks = await retriever.retrieve(data.question)
            answer = await answer_question(data.question, chunks, llm, settings.relevance_threshold)
        except (EmbeddingError, httpx.HTTPError, ValidationError) as exc:
            logger.warning("model_unavailable")
            raise HTTPException(503, "Сервис модели недоступен. Повторите позже.") from exc
    logger.info("consultation_processed", extra={"question_length": len(data.question)})
    return await repo.save(db, owner[0], data.question, answer)


@app.patch("/api/consultations/{key}", status_code=204)
async def vote(key: UUID, data: Vote, db: Database, owner: Owner) -> None:
    """Сохраняет оценку ответа."""
    if not await repo.vote(db, owner[0], key, data.helpful):
        raise HTTPException(404, "Консультация не найдена")


@app.delete("/api/consultations/{key}", status_code=204)
async def remove(key: UUID, db: Database, owner: Owner) -> None:
    """Удаляет консультацию владельца."""
    if not await repo.remove(db, owner[0], key):
        raise HTTPException(404, "Консультация не найдена")
