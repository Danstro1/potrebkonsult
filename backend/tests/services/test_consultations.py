from uuid import uuid4

import pytest

from app.rag.retriever import ScoredChunk
from app.services.consultations import answer_question
from tests.fakes import FakeLLMClient


@pytest.mark.anyio
@pytest.mark.parametrize(
    "score,reply,refusal",
    [
        (0.5, "Ответ [1]", True),
        (0.7, "Ответ [1]", False),
        (0.7, "Можно обжаловать отказ магазина [1].", False),
        (0.7, "Ответ [2]", True),
        (0.7, "Без ссылки", True),
        (0.7, "ОТКАЗ", True),
    ],
)
async def test_grounding(score: float, reply: str, refusal: bool) -> None:
    chunk = ScoredChunk(uuid4(), "Закон", "18", None, 1, "Выдержка", score)
    llm = FakeLLMClient(reply)
    result = await answer_question("Вопрос", [chunk], llm, 0.5)
    assert result.refusal is refusal
    assert bool(result.sources) is not refusal
    assert len(llm.prompts) == int(score > 0.5)
