"""Оценка качества поиска на контрольных вопросах: Recall@k и MRR.

Запуск из папки backend:
    python -m app.rag.evaluate --questions ../data/eval/control_questions.json \
        --output ../data/eval/retrieval_report.md
"""

import argparse
import asyncio
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, TypeAdapter

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.rag.embedder import OllamaEmbedder
from app.rag.retriever import ScoredChunk, VectorRetriever

logger = logging.getLogger(__name__)


class ControlQuestion(BaseModel):
    """Контрольный вопрос с номерами статей, которые должны найтись."""

    question: str = Field(min_length=1)
    expected_articles: list[str] = Field(min_length=1)
    note: str | None = None


@dataclass(frozen=True, slots=True)
class EvalRow:
    """Результат поиска по одному контрольному вопросу."""

    question: ControlQuestion
    found: list[ScoredChunk]
    hit: bool
    reciprocal_rank: float


def score_ranking(expected: Sequence[str], found_articles: Sequence[str | None]) -> float:
    """Считает обратный ранг первой ожидаемой статьи в выдаче.

    Args:
        expected: Номера статей, любая из которых считается правильным ответом.
        found_articles: Номера статей найденных фрагментов в порядке выдачи.

    Returns:
        1/позиция первого попадания или 0.0, если ожидаемой статьи нет.
    """
    for position, article in enumerate(found_articles, start=1):
        if article is not None and article in expected:
            return 1.0 / position
    return 0.0


def summarize(rows: Sequence[EvalRow]) -> tuple[float, float]:
    """Считает итоговые метрики по всем вопросам.

    Args:
        rows: Результаты по вопросам.

    Returns:
        Пара (Recall@k, MRR); для пустого набора — (0.0, 0.0).
    """
    if not rows:
        return 0.0, 0.0
    recall = sum(row.hit for row in rows) / len(rows)
    mrr = sum(row.reciprocal_rank for row in rows) / len(rows)
    return recall, mrr


def load_questions(path: Path) -> list[ControlQuestion]:
    """Читает контрольные вопросы из JSON-файла.

    Args:
        path: Путь к JSON-массиву объектов ControlQuestion.

    Returns:
        Провалидированные вопросы.
    """
    adapter = TypeAdapter(list[ControlQuestion])
    return adapter.validate_python(json.loads(path.read_text(encoding="utf-8")))


def _format_found(chunk: ScoredChunk) -> str:
    article = f"ст. {chunk.article}" if chunk.article else "преамбула"
    part = f" ч.{chunk.part}" if chunk.part > 1 else ""
    return f"{article}{part} ({chunk.score:.3f})"


def render_report(rows: Sequence[EvalRow], top_k: int) -> str:
    """Формирует отчёт в Markdown: таблица по вопросам и итоговые метрики.

    Args:
        rows: Результаты по вопросам.
        top_k: Глубина выдачи, по которой считался Recall.

    Returns:
        Текст отчёта.
    """
    recall, mrr = summarize(rows)
    lines = [
        f"# Оценка поиска (Recall@{top_k}), {date.today().isoformat()}",
        "",
        f"| # | Вопрос | Ожидаемые статьи | Найденные топ-{top_k} (сходство) | Попадание |",
        "|---|---|---|---|---|",
    ]
    for number, row in enumerate(rows, start=1):
        expected = ", ".join(f"ст. {a}" for a in row.question.expected_articles)
        found = "; ".join(_format_found(chunk) for chunk in row.found)
        lines.append(
            f"| {number} | {row.question.question} | {expected} | {found} | "
            f"{'да' if row.hit else 'нет'} |"
        )
    hits = sum(row.hit for row in rows)
    lines += [
        "",
        f"**Recall@{top_k}:** {hits} из {len(rows)} = {recall:.2f}  ",
        f"**MRR:** {mrr:.3f}",
    ]
    return "\n".join(lines) + "\n"


async def evaluate(
    retriever: VectorRetriever, questions: Sequence[ControlQuestion], top_k: int
) -> list[EvalRow]:
    """Прогоняет контрольные вопросы через поиск.

    Args:
        retriever: Поисковик.
        questions: Контрольные вопросы.
        top_k: Сколько фрагментов брать в выдаче.

    Returns:
        Результаты по каждому вопросу.
    """
    rows: list[EvalRow] = []
    for question in questions:
        found = await retriever.retrieve(question.question, top_k=top_k)
        rank = score_ranking(question.expected_articles, [chunk.article for chunk in found])
        rows.append(EvalRow(question=question, found=found, hit=rank > 0, reciprocal_rank=rank))
    return rows


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    questions = load_questions(args.questions)
    engine = create_engine(settings.database_url)
    try:
        async with httpx.AsyncClient() as client:
            embedder = OllamaEmbedder(
                client,
                settings.ollama_base_url,
                model=settings.embedding_model,
                timeout_seconds=settings.embedding_timeout_seconds,
            )
            retriever = VectorRetriever(create_session_factory(engine), embedder)
            rows = await evaluate(retriever, questions, args.top_k)
    finally:
        await engine.dispose()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(rows, args.top_k), encoding="utf-8")
    recall, mrr = summarize(rows)
    logger.info(
        "retrieval_eval_done",
        extra={
            "questions": len(rows),
            "top_k": args.top_k,
            "recall": round(recall, 3),
            "mrr": round(mrr, 3),
            "report": str(args.output),
        },
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Точка входа CLI оценки поиска.

    Args:
        argv: Аргументы командной строки (по умолчанию — sys.argv).
    """
    parser = argparse.ArgumentParser(description="Оценка поиска на контрольных вопросах")
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    configure_logging()
    asyncio.run(_run(parser.parse_args(argv)))


if __name__ == "__main__":
    main()
