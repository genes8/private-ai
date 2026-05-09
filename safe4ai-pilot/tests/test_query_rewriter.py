from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.query_rewriter import QueryRewriter


def _make_rewriter() -> QueryRewriter:
    return QueryRewriter(ollama_url="http://localhost:11434", model="qwen3.5:9b")


@pytest.mark.asyncio
async def test_rewrite_success() -> None:
    rewriter = _make_rewriter()
    original = "what is the revenue?"
    rewritten = "The company revenue for 2023 was $10M..."

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": rewritten}

    with patch("app.services.query_rewriter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await rewriter.rewrite(original)

    assert result != ""
    assert result == rewritten


@pytest.mark.asyncio
async def test_rewrite_fallback_on_error() -> None:
    rewriter = _make_rewriter()
    original = "what is the revenue?"

    with patch("app.services.query_rewriter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        mock_client_cls.return_value = mock_client

        result = await rewriter.rewrite(original)

    assert result == original
