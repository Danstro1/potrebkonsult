import uuid
from pathlib import Path

import pytest

from app.rag.evaluate import (
    ControlQuestion,
    EvalRow,
    load_questions,
    render_report,
    score_ranking,
    summarize,
)
from app.rag.retriever import ScoredChunk

QUESTIONS_FILE = Path(__file__).resolve().parents[3] / "data" / "eval" / "control_questions.json"


def _found(article: str | None, score: float = 0.5, part: int = 1) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_title="Закон",
        article=article,
        article_title=None,
        part=part,
        content="Текст.",
        score=score,
    )


@pytest.mark.parametrize(
    ("expected", "found", "rank"),
    [
        (["18"], ["18", "19"], 1.0),
        (["18"], ["25", None, "18"], 1 / 3),
        (["22", "23"], ["23.1", "23", "22"], 0.5),
        (["18"], ["25", "19"], 0.0),
        (["18"], [], 0.0),
    ],
)
def test_score_ranking(expected: list[str], found: list[str | None], rank: float) -> None:
    assert score_ranking(expected, found) == pytest.approx(rank)


def test_summarize_computes_recall_and_mrr() -> None:
    question = ControlQuestion(question="Вопрос", expected_articles=["18"])
    rows = [
        EvalRow(question=question, found=[], hit=True, reciprocal_rank=1.0),
        EvalRow(question=question, found=[], hit=True, reciprocal_rank=0.5),
        EvalRow(question=question, found=[], hit=False, reciprocal_rank=0.0),
    ]

    assert summarize(rows) == pytest.approx((2 / 3, 0.5))
    assert summarize([]) == (0.0, 0.0)


def test_render_report_contains_rows_and_totals() -> None:
    question = ControlQuestion(question="Можно ли вернуть носки?", expected_articles=["25"])
    row = EvalRow(
        question=question,
        found=[_found("18", 0.61, part=7), _found(None, 0.55), _found("25", 0.53)],
        hit=True,
        reciprocal_rank=1 / 3,
    )

    report = render_report([row], top_k=5)

    assert "| 1 | Можно ли вернуть носки? | ст. 25 |" in report
    assert "ст. 18 ч.7 (0.610); преамбула (0.550); ст. 25 (0.530) | да |" in report
    assert "**Recall@5:** 1 из 1 = 1.00" in report
    assert "**MRR:** 0.333" in report


def test_control_questions_file_is_valid() -> None:
    questions = load_questions(QUESTIONS_FILE)

    assert len(questions) == 10
    assert len({q.question for q in questions}) == 10
