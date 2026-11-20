"""Контракты HTTP API консультаций."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints


class Credentials(BaseModel):
    username: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z0-9_-]{3,64}$")
    ]
    password: str = Field(min_length=10, max_length=128)


class Question(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
    ]


class Vote(BaseModel):
    helpful: bool


class Source(BaseModel):
    title: str
    excerpt: str


class Answer(BaseModel):
    text: str
    refusal: bool
    sources: list[Source]


class Consultation(Question):
    id: UUID
    answer: Answer
    helpful: bool | None


class Identity(BaseModel):
    username: str
