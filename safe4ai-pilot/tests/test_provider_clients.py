from __future__ import annotations

import pytest
import httpx

from app.services.provider_clients import (
    OpenAICompatibleProvider,
    ProviderUsage,
)


@pytest.mark.asyncio
async def test_openai_compatible_chat_extracts_actual_usage() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Answer text"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        chat_model="deepseek-chat",
        embedding_model="text-embedding-3-small",
        vision_model="qwen-vl",
        client=client,
    )

    result = await provider.chat("System", "Question")

    assert result.content == "Answer text"
    assert result.usage == ProviderUsage(
        prompt_tokens=11, completion_tokens=7, total_tokens=18, source="actual"
    )
    assert str(requests[0].url) == "https://api.example.com/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_openai_compatible_embeddings_reads_embedding_vector() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        chat_model="qwen-plus",
        embedding_model="text-embedding-3-small",
        vision_model="qwen-vl",
        client=client,
    )

    assert await provider.embed_query("hello") == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_openai_compatible_embed_documents_batch() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        chat_model="qwen-plus",
        embedding_model="text-embedding-3-small",
        vision_model="qwen-vl",
        client=client,
    )

    result = await provider.embed_documents(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
