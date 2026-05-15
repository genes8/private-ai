from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import httpx


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OllamaEmbeddingProvider:
    """Calls the Ollama /api/embed endpoint for a single text."""

    def __init__(self, ollama_url: str, model: str) -> None:
        self._ollama_url = ollama_url
        self._model = model

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._ollama_url}/api/embed",
                json={"model": self._model, "input": text},
                timeout=30.0,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            embedding = data.get("embedding") or data.get("embeddings", [None])[0]
            if not isinstance(embedding, list):
                raise ValueError("Ollama embed response did not include an embedding list")
            return [float(v) for v in embedding]
