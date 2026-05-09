from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import RouterDecision
from app.services.query_router import QueryRouter


def _make_router() -> QueryRouter:
    return QueryRouter(ollama_url="http://localhost:11434", model="qwen3.5:9b")


@pytest.mark.asyncio
async def test_route_empty_collections_returns_no_route() -> None:
    router = _make_router()
    result = await router.route(query="anything", available_collections=[])
    assert result.collection == ""
    assert result.confidence == 0.0
    assert "no collections" in result.reason


@pytest.mark.asyncio
async def test_route_session_collection_takes_priority() -> None:
    router = _make_router()
    result = await router.route(
        query="anything",
        available_collections=["col-a", "col-b"],
        session_collection="col-b",
    )
    assert result.collection == "col-b"
    assert result.confidence == 1.0
    assert "session" in result.reason.lower()


@pytest.mark.asyncio
async def test_route_single_collection() -> None:
    router = _make_router()
    result = await router.route(
        query="anything",
        available_collections=["only-col"],
    )
    assert result.collection == "only-col"
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_route_llm_decides() -> None:
    router = _make_router()
    llm_payload = json.dumps({"collection": "col-b", "confidence": 0.85, "reason": "best match"})

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": llm_payload}

    with patch("app.services.query_router.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await router.route(
            query="show me contracts",
            available_collections=["col-a", "col-b"],
        )

    assert isinstance(result, RouterDecision)
    assert result.collection == "col-b"
    assert result.confidence == 0.85
    assert result.reason == "best match"


@pytest.mark.asyncio
async def test_route_parse_error_fallback() -> None:
    router = _make_router()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "not valid json {{{"}

    with patch("app.services.query_router.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await router.route(
            query="show me stuff",
            available_collections=["col-a", "col-b"],
        )

    assert result.collection == "col-a"
    assert result.confidence == 0.5
    assert "fallback" in result.reason.lower()
