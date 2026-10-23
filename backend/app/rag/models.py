"""Модели данных RAG-конвейера (без зависимостей от FastAPI)."""

from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    """Фрагмент нормативного документа — единица векторного поиска и цитирования.

    Базовый фрагмент — статья целиком; статья длиннее лимита делится на части
    по пунктам, и каждая часть хранит номер и название своей статьи.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    document_title: str = Field(
        min_length=1,
        description="Название документа для ссылки в ответе, например "
        "«Закон РФ „О защите прав потребителей“».",
    )
    article: str | None = Field(
        default=None,
        pattern=r"^\d+(\.\d+)*$",
        description="Номер статьи строкой: в законе есть статьи вида «23.1». "
        "None — преамбула или текст вне статей.",
    )
    article_title: str | None = Field(
        default=None,
        description="Название статьи без номера; нужно для карточки источника "
        "и улучшает эмбеддинг коротких фрагментов.",
    )
    part: int = Field(
        default=1,
        ge=1,
        description="Порядковый номер части статьи (1, если статья не делилась).",
    )
    content: str = Field(
        min_length=1,
        description="Текст фрагмента без заголовка статьи и редакционных пометок.",
    )

    def heading(self) -> str:
        """Возвращает заголовок для карточки источника.

        Returns:
            «Статья N. Название» или «Преамбула» для текста вне статей.
        """
        if self.article is None:
            return "Преамбула"
        if self.article_title:
            return f"Статья {self.article}. {self.article_title}"
        return f"Статья {self.article}"

    def embedding_text(self) -> str:
        """Возвращает текст, по которому считается эмбеддинг.

        Заголовок добавляется к каждой части статьи: без него часть из середины
        статьи теряет тему, и поиск по бытовому вопросу её не находит.

        Returns:
            Название документа, заголовок и текст фрагмента через перевод строки.
        """
        return f"{self.document_title}\n{self.heading()}\n{self.content}"
