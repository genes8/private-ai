from __future__ import annotations

import httpx
import pytest

from app.services.provider_clients import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_openai_provider_describe_image_uses_multimodal_payload() -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = __import__("json").loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "Extracted text"},
                            ]
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://api.example.test/v1",
            api_key="secret",
            chat_model="chat-model",
            embedding_model="embed-model",
            vision_model="vision-model",
            client=client,
        )
        result = await provider.describe_image("Read this page", "ZmFrZS1iNjQ=")

    assert result == "Extracted text"
    assert captured_payload["model"] == "vision-model"
    messages = captured_payload["messages"]
    assert isinstance(messages, list)
    content = messages[0]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/png;base64,ZmFrZS1iNjQ="
