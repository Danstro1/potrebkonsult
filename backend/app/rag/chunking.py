"""Нарезка текста закона на фрагменты по статьям и пунктам."""

import re
from collections.abc import Sequence

from app.rag.models import Chunk

DEFAULT_MAX_CHARS = 1500

# Точка после номера обязательна: так ссылки вида «Статья 18 настоящего Закона»
# в начале абзаца не принимаются за заголовок.
_ARTICLE_HEADER_RE = re.compile(r"^Статья\s+(\d+(?:\.\d+)*)\.\s*(.*)$")
_POINT_START_RE = re.compile(r"^\d+(?:\.\d+)*\.\s")
_CHAPTER_HEADER_RE = re.compile(r"^Глава\s+[IVXLC]+\.")
_REPEALED_TITLE_RE = re.compile(r"^Утратил\w*\s+силу", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"(?<=[.;:!?])\s+")
_WHITESPACE_RE = re.compile(r"\s+")

# Строки, которые справочные системы (КонсультантПлюс, Гарант) вставляют в текст закона.
# Нормой они не являются, а в эмбеддингах дают шум: пометки о редакциях одинаковы
# у десятков статей и «склеивают» их в векторном пространстве.
_EDITORIAL_NOTE_START_RE = re.compile(
    r"^\((?:в ред\.|см\.|п\.|пп\.|абз|часть|введен|утратил|с изм\.)", re.IGNORECASE
)
# Примечание справочной системы — заголовок и ровно один абзац комментария после него.
_PUBLISHER_NOTE_RE = re.compile(r"^КонсультантПлюс: примечание\.?$")
_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^(?:\d+(?:\.\d+)*\.\s*)?(?:Абзацы?\b[^.]*?)?(?:утратил\w*\s+силу|исключен\.)",
        re.IGNORECASE,
    ),
    re.compile(r"^Список изменяющих документов$"),
    re.compile(r"^Перспективы и риски "),
    re.compile(r"^(?:Арбитражные споры|Споры в суде общей юрисдикции):$"),
    re.compile(r"^См\. все ситуации"),
    re.compile(r"^Позиции высших судов"),
    # В тексте закона перечни оформлены абзацами с «;», а строки с дефисом —
    # навигационные ссылки справочной системы («- Покупатель хочет…»).
    re.compile(r"^- "),
    re.compile(r">>>$"),
)


def normalize_law_text(text: str) -> str:
    """Очищает текст закона от служебных строк справочных систем.

    Удаляет пометки о редакциях, утратившие силу пункты и абзацы, навигационные
    вставки; схлопывает пробелы (включая неразрывные) и пустые строки.

    Args:
        text: Исходный текст документа.

    Returns:
        Текст, где каждая строка — один абзац нормы.
    """
    lines: list[str] = []
    # Пометка о редакции может занимать несколько строк (список изменяющих законов
    # в начале документа), поэтому пропускаем до закрытия скобки, а не одну строку.
    open_parens = 0
    skip_note_body = False
    for raw_line in text.splitlines():
        line = _WHITESPACE_RE.sub(" ", raw_line).strip()
        if not line:
            continue
        if skip_note_body:
            skip_note_body = False
            continue
        if _PUBLISHER_NOTE_RE.match(line):
            skip_note_body = True
            continue
        if open_parens > 0 or _EDITORIAL_NOTE_START_RE.match(line):
            open_parens = max(open_parens + line.count("(") - line.count(")"), 0)
            continue
        if not any(pattern.search(line) for pattern in _NOISE_PATTERNS):
            lines.append(line)
    return "\n".join(lines)


def split_law_into_articles(
    text: str, document_title: str, max_chars: int = DEFAULT_MAX_CHARS
) -> list[Chunk]:
    """Делит текст закона на фрагменты для векторного поиска.

    Статья становится одним фрагментом, если укладывается в лимит. Длинная статья
    делится по пунктам (соседние пункты объединяются, пока влезают), пункт длиннее
    лимита — по абзацам, абзац длиннее лимита — по предложениям. Текст до первой
    статьи (преамбула) — отдельный фрагмент с ``article=None``. Заголовки глав
    и утратившие силу статьи в фрагменты не попадают.

    Args:
        text: Текст закона.
        document_title: Название документа для ссылок на источник.
        max_chars: Максимальная длина текста фрагмента в символах.

    Returns:
        Фрагменты в порядке следования в документе.

    Raises:
        ValueError: Если лимит не положителен или название документа пустое.
    """
    if max_chars <= 0:
        raise ValueError("max_chars должен быть положительным")
    if not document_title.strip():
        raise ValueError("Не указано название документа")

    chunks: list[Chunk] = []
    preamble: list[str] = []
    article: str | None = None
    article_title: str | None = None
    body: list[str] = []
    seen_article = False

    def flush() -> None:
        if not seen_article:
            lines, number, title = preamble, None, None
        else:
            lines, number, title = body, article, article_title
        if not lines or (title is not None and _REPEALED_TITLE_RE.match(title)):
            return
        for index, content in enumerate(_split_body(lines, max_chars), start=1):
            chunks.append(
                Chunk(
                    document_title=document_title,
                    article=number,
                    article_title=title,
                    part=index,
                    content=content,
                )
            )

    for line in normalize_law_text(text).split("\n"):
        if not line or _CHAPTER_HEADER_RE.match(line):
            continue
        header = _ARTICLE_HEADER_RE.match(line)
        if header:
            flush()
            seen_article = True
            article, article_title, body = header.group(1), header.group(2) or None, []
        elif seen_article:
            body.append(line)
        else:
            preamble.append(line)
    flush()
    return chunks


def _split_body(lines: Sequence[str], max_chars: int) -> list[str]:
    if len("\n".join(lines)) <= max_chars:
        return ["\n".join(lines)]
    units: list[str] = []
    for point in _group_points(lines):
        point_text = "\n".join(point)
        if len(point_text) <= max_chars:
            units.append(point_text)
            continue
        for paragraph in point:
            if len(paragraph) <= max_chars:
                units.append(paragraph)
            else:
                units.extend(_split_paragraph(paragraph, max_chars))
    return _pack(units, max_chars, separator="\n")


def _group_points(lines: Sequence[str]) -> list[list[str]]:
    # Абзацы до первого пункта (вводная часть статьи) образуют отдельную группу.
    groups: list[list[str]] = []
    for line in lines:
        if not groups or _POINT_START_RE.match(line):
            groups.append([line])
        else:
            groups[-1].append(line)
    return groups


def _split_paragraph(paragraph: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    for sentence in _SENTENCE_END_RE.split(paragraph):
        while len(sentence) > max_chars:
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if sentence:
            pieces.append(sentence)
    return _pack(pieces, max_chars, separator=" ")


def _pack(units: Sequence[str], max_chars: int, separator: str) -> list[str]:
    parts: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) + len(separator) + len(unit) <= max_chars:
            current = f"{current}{separator}{unit}"
        else:
            parts.append(current)
            current = unit
    if current:
        parts.append(current)
    return parts
