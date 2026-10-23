from pathlib import Path

import pytest

from app.rag.chunking import normalize_law_text, split_law_into_articles
from app.rag.models import Chunk

TITLE = "Закон РФ «О защите прав потребителей»"
# Преамбула, статьи 18, 19 и 25 в выгрузке КонсультантПлюс (ред. от 28.12.2025)
# вместе со служебными строками справочной системы.
FIXTURE = Path(__file__).parent / "fixtures" / "zozpp_excerpt.txt"


def _point(number: str, length: int) -> str:
    return f"{number}. " + "Текст пункта " * (length // 13)


def test_short_article_becomes_single_chunk() -> None:
    text = (
        "Статья 25. Право потребителя на обмен товара надлежащего качества\n"
        "1. Потребитель вправе обменять непродовольственный товар.\n"
        "2. Если аналогичный товар отсутствует, потребитель вправе вернуть деньги."
    )

    chunks = split_law_into_articles(text, TITLE)

    assert chunks == [
        Chunk(
            document_title=TITLE,
            article="25",
            article_title="Право потребителя на обмен товара надлежащего качества",
            part=1,
            content="1. Потребитель вправе обменять непродовольственный товар.\n"
            "2. Если аналогичный товар отсутствует, потребитель вправе вернуть деньги.",
        )
    ]


def test_long_article_is_split_by_points_and_keeps_article_number() -> None:
    points = [_point(str(n), 700) for n in range(1, 5)]
    text = "Статья 18. Права потребителя\n" + "\n".join(points)

    chunks = split_law_into_articles(text, TITLE, max_chars=1500)

    assert [c.part for c in chunks] == [1, 2]
    assert all(c.article == "18" and c.article_title == "Права потребителя" for c in chunks)
    assert all(len(c.content) <= 1500 for c in chunks)
    assert chunks[0].content.startswith("1. ")
    assert chunks[1].content.startswith("3. ")


def test_preamble_is_separate_chunk_without_article() -> None:
    text = (
        "Настоящий Закон регулирует отношения между потребителями и продавцами.\n"
        "Статья 1. Правовое регулирование\n"
        "1. Отношения регулируются Гражданским кодексом."
    )

    chunks = split_law_into_articles(text, TITLE)

    assert chunks[0].article is None
    assert chunks[0].article_title is None
    assert chunks[0].heading() == "Преамбула"
    assert chunks[0].content.startswith("Настоящий Закон регулирует")
    assert chunks[1].article == "1"


@pytest.mark.parametrize("text", ["", "   \n\t\n  "])
def test_empty_text_gives_no_chunks(text: str) -> None:
    assert split_law_into_articles(text, TITLE) == []


def test_point_longer_than_limit_is_split_by_paragraphs() -> None:
    paragraphs = ["1. Вводный абзац пункта."] + [f"абзац {n} " + "x" * 600 for n in range(3)]
    text = "Статья 18. Права потребителя\n" + "\n".join(paragraphs)

    chunks = split_law_into_articles(text, TITLE, max_chars=1000)

    assert len(chunks) == 3
    assert all(len(c.content) <= 1000 for c in chunks)
    assert chunks[0].content.startswith("1. Вводный абзац пункта.\nабзац 0")


def test_paragraph_longer_than_limit_is_split_by_sentences() -> None:
    sentence = "Предложение нормы " + "о" * 80 + "."
    text = "Статья 2. Длинный абзац\n" + " ".join([sentence] * 10)

    chunks = split_law_into_articles(text, TITLE, max_chars=250)

    assert len(chunks) > 1
    assert all(len(c.content) <= 250 for c in chunks)
    assert all(c.content.endswith(".") for c in chunks)


def test_dotted_article_numbers_are_recognized() -> None:
    text = "Статья 23.1. Последствия нарушения срока передачи\n1. Текст."

    chunks = split_law_into_articles(text, TITLE)

    assert chunks[0].article == "23.1"
    assert chunks[0].heading() == "Статья 23.1. Последствия нарушения срока передачи"


def test_reference_to_article_is_not_treated_as_header() -> None:
    text = (
        "Статья 19. Сроки\n"
        "Статья 18 настоящего Закона применяется с учетом сроков.\n"
        "В соответствии со статьей 18. потребитель вправе..."
    )

    chunks = split_law_into_articles(text, TITLE)

    assert [c.article for c in chunks] == ["19"]
    assert "Статья 18 настоящего Закона" in chunks[0].content


def test_chapter_headers_and_repealed_articles_are_skipped() -> None:
    text = (
        "Глава II. ЗАЩИТА ПРАВ ПОТРЕБИТЕЛЕЙ ПРИ ПРОДАЖЕ ТОВАРОВ\n"
        "Статья 17. Утратила силу. - Федеральный закон от 01.01.2000 N 1-ФЗ.\n"
        "Статья 18. Права потребителя\n"
        "1. Текст."
    )

    chunks = split_law_into_articles(text, TITLE)

    assert [c.article for c in chunks] == ["18"]
    assert "Глава" not in chunks[0].content


def test_normalize_removes_editorial_noise() -> None:
    text = (
        "Список изменяющих документов\n"
        "(в ред. Федеральных законов от 09.01.1996 N 2-ФЗ,\n"
        "от 02.12.2019 N 425-ФЗ (ред. 22.12.2020),\n"
        "от 28.12.2025 N 500-ФЗ)\n"
        "1. Потребитель вправе потребовать замены товара.\n"
        "(п. 1 в ред. Федерального закона от 25.10.2007 N 234-ФЗ)\n"
        "(см. текст в предыдущей редакции)\n"
        "Перспективы и риски споров в суде общей юрисдикции. Ситуации, связанные со ст. 18\n"
        "- Покупатель хочет взыскать деньги\n"
        "4. Утратил силу. - Федеральный закон от 25.10.2007 N 234-ФЗ.\n"
        "Абзац утратил силу. - Федеральный закон от 17.12.1999 N 212-ФЗ.\n"
        "5. Отсутствие   у потребителя чека не является основанием для отказа."
    )

    assert normalize_law_text(text) == (
        "1. Потребитель вправе потребовать замены товара.\n"
        "5. Отсутствие у потребителя чека не является основанием для отказа."
    )


def test_normalize_removes_publisher_notes_and_navigation() -> None:
    text = (
        "КонсультантПлюс: примечание.\n"
        "С 01.03.2027 ст. 6 излагается в новой редакции. См. будущую редакцию.\n"
        "Статья 6. Обязанность изготовителя\n"
        "Перспективы и риски арбитражных споров и споров в суде общей юрисдикции.\n"
        "Арбитражные споры:\n"
        "Споры в суде общей юрисдикции:\n"
        "См. все ситуации, связанные со ст. 28\n"
        "Абзац исключен. - Федеральный закон от 17.12.1999 N 212-ФЗ.\n"
        "Исключение составляют случаи, предусмотренные договором."
    )

    assert normalize_law_text(text) == (
        "Статья 6. Обязанность изготовителя\n"
        "Исключение составляют случаи, предусмотренные договором."
    )


def test_embedding_text_includes_document_and_heading() -> None:
    chunk = Chunk(
        document_title=TITLE,
        article="18",
        article_title="Права потребителя",
        part=2,
        content="Текст.",
    )

    assert chunk.embedding_text() == f"{TITLE}\nСтатья 18. Права потребителя\nТекст."


@pytest.mark.parametrize(
    ("max_chars", "title"),
    [(0, TITLE), (-5, TITLE), (1500, "   ")],
    ids=["zero-limit", "negative-limit", "blank-title"],
)
def test_invalid_arguments_raise(max_chars: int, title: str) -> None:
    with pytest.raises(ValueError):
        split_law_into_articles("Статья 1. Т\nТекст.", title, max_chars=max_chars)


def test_real_law_excerpt() -> None:
    chunks = split_law_into_articles(FIXTURE.read_text(encoding="utf-8"), TITLE)

    articles = {c.article for c in chunks}
    assert articles == {None, "18", "19", "25"}
    assert all(len(c.content) <= 1500 for c in chunks)
    noise = ("(в ред.", "(см. текст", "утратил силу", "Перспективы и риски", "\n- ")
    assert not [c for c in chunks if any(n in c.content for n in noise)]

    by_article = {a: [c for c in chunks if c.article == a] for a in articles}
    assert [c.part for c in by_article["18"]] == list(range(1, len(by_article["18"]) + 1))
    assert by_article["18"][0].content.startswith("1. Потребитель в случае обнаружения")
    assert any("существенный недостаток товара" in c.content for c in by_article[None])
    assert "Статья 19. Сроки предъявления" in by_article["19"][0].embedding_text()
