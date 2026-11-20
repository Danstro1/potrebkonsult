"""Генерация локальной моделью Ollama."""

import httpx
from pydantic import BaseModel


class _Completion(BaseModel):
    response: str


class OllamaClient:
    def __init__(self, client: httpx.AsyncClient, url: str, model: str) -> None:
        self.client = client
        self.url = url.rstrip("/") + "/api/generate"
        self.model = model

    async def complete(self, prompt: str) -> str:
        """Возвращает полный ответ локальной модели."""
        result = await self.client.post(
            self.url,
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        result.raise_for_status()
        return _Completion.model_validate(result.json()).response.strip()
