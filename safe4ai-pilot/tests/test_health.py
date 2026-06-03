"""Smoke tests for /health endpoint and prompt registry."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _mock_engine_connect() -> MagicMock:
    """Context manager that simulates a successful DB connection."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute = MagicMock(return_value=None)
    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)
    return mock_engine


@pytest.fixture
def client_with_mocks() -> Generator[TestClient, None, None]:
    """TestClient with all external dependencies mocked."""
    from app.main import app

    mock_engine = _mock_engine_connect()
    mock_db = MagicMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__enter__.return_value = mock_db
    mock_session_ctx.__exit__.return_value = False

    # Mock qdrant + ollama HTTP calls
    async def mock_get(url: str, **_kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        return resp

    with (
        patch("app.main.engine", mock_engine),
        patch("app.main.SessionLocal", return_value=mock_session_ctx),
        patch("app.main.load_runtime_config", return_value=MagicMock(provider_type="ollama")),
        patch("httpx.AsyncClient.get", mock_get),
    ):
        yield TestClient(app)


def test_health_returns_200(client_with_mocks: TestClient) -> None:
    r = client_with_mocks.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "checks" in body


def test_health_uses_provider_check_for_openai_compatible() -> None:
    from app.main import app

    mock_engine = _mock_engine_connect()

    async def mock_get(_self: object, url: str, **_kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.url = url
        return resp

    with (
        patch("app.main.engine", mock_engine),
        patch("app.main.load_runtime_config") as mock_runtime_config,
        patch("httpx.AsyncClient.get", mock_get),
    ):
        mock_runtime_config.return_value = MagicMock(
            provider_type="openai_compatible",
            provider_base_url="https://api.example.test/v1",
            provider_api_key="secret",
        )
        client = TestClient(app)
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "provider" in body["checks"]
    assert body["checks"]["provider"] == "ok"


def test_health_provider_check_uses_pinned_transport_when_resolved_ip_exists() -> None:
    from app.main import app

    mock_engine = _mock_engine_connect()
    pinned_transport = object()
    client_kwargs: list[dict[str, object]] = []

    class _FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            client_kwargs.append(kwargs)

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, _url: str, **_kwargs: object) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 200
            return resp

    with (
        patch("app.main.engine", mock_engine),
        patch("app.main.load_runtime_config") as mock_runtime_config,
        patch("app.main.create_pinned_async_transport", return_value=pinned_transport),
        patch("app.main.httpx.AsyncClient", _FakeAsyncClient),
    ):
        mock_runtime_config.return_value = MagicMock(
            provider_type="openai_compatible",
            provider_base_url="https://api.example.test/v1",
            provider_resolved_ip="93.184.216.34",
            provider_api_key="secret",
        )
        client = TestClient(app)
        response = client.get("/health")

    assert response.status_code == 200
    assert {"timeout": 5, "transport": pinned_transport} in client_kwargs


def test_prompt_registry_get_latest() -> None:
    from app.prompts.registry import get_prompt

    pt = get_prompt("query_rewriter")
    assert pt.name == "query_rewriter"
    assert "{query}" in pt.template


def test_prompt_registry_get_by_version() -> None:
    from app.prompts.registry import get_prompt

    pt = get_prompt("document_grader", "v1")
    assert pt.version == "v1"


def test_prompt_registry_missing_raises() -> None:
    from app.prompts.registry import get_prompt

    with pytest.raises(KeyError):
        get_prompt("nonexistent_prompt")


def test_guard_result_model() -> None:
    from app.models import GuardResult

    g = GuardResult(allowed=True, reason="ok")
    assert g.allowed is True


def test_router_decision_model() -> None:
    from app.models import RouterDecision

    rd = RouterDecision(collection="docs", confidence=0.95, reason="exact match")
    assert rd.collection == "docs"
