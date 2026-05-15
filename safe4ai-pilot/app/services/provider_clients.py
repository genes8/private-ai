from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    source: str


@dataclass(frozen=True)
class ChatResult:
    content: str
    usage: ProviderUsage | None = None


class ChatClient(Protocol):
    async def chat(self, system_prompt: str, user_prompt: str) -> ChatResult: ...


class EmbeddingClient(Protocol):
    async def embed_query(self, query: str) -> list[float]: ...
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class VisionClient(Protocol):
    async def describe_image(self, prompt: str, image_b64: str) -> str: ...


def _usage_from_openai(payload: dict[str, Any]) -> ProviderUsage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return ProviderUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        source="actual",
    )


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        vision_model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._vision_model = vision_model
        self._client = client or httpx.AsyncClient(timeout=60)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def chat(self, system_prompt: str, user_prompt: str) -> ChatResult:
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self._chat_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return ChatResult(content=str(content), usage=_usage_from_openai(payload))

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_documents([query])
        return vectors[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            f"{self._base_url}/embeddings",
            headers=self._headers(),
            json={"model": self._embedding_model, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
        return [list(item["embedding"]) for item in payload.get("data", [])]

    async def describe_image(self, prompt: str, image_b64: str) -> str:
        result = await self.chat(prompt, image_b64)
        return result.content


class OllamaProvider:
    def __init__(
        self,
        *,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        vision_model: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._vision_model = vision_model

    async def chat(self, system_prompt: str, user_prompt: str) -> ChatResult:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._chat_model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False,
                },
            )
        response.raise_for_status()
        return ChatResult(content=str(response.json().get("response", "")), usage=None)

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_documents([query])
        return vectors[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._embedding_model, "input": texts},
                )
                if response.status_code < 400:
                    response.raise_for_status()
                    embeddings = response.json().get("embeddings", [])
                    return [list(v) for v in embeddings]
            except (httpx.HTTPStatusError, httpx.RequestError):
                pass

            # Fallback: call legacy /api/embeddings one at a time
            vectors: list[list[float]] = []
            for text in texts:
                fallback = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._embedding_model, "prompt": text},
                )
                fallback.raise_for_status()
                vectors.append(list(fallback.json()["embedding"]))
            return vectors

    async def describe_image(self, prompt: str, image_b64: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._vision_model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                },
            )
        response.raise_for_status()
        return str(response.json().get("response", ""))

    async def chat_raw(
        self,
        prompt: str,
        *,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> str:
        """Low-level Ollama generate call returning raw response text (for graph nodes)."""
        async def _call(c: httpx.AsyncClient) -> str:
            resp = await c.post(
                f"{self._base_url}/api/generate",
                json={"model": self._chat_model, "prompt": prompt, "stream": False},
                timeout=timeout,
            )
            resp.raise_for_status()
            return str(resp.json().get("response", ""))

        if client is not None:
            return await _call(client)
        async with httpx.AsyncClient() as c:
            return await _call(c)
