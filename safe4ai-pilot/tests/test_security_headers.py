"""Tests for security headers added by the secure middleware."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app.db import get_db


def _mock_engine_connect() -> MagicMock:
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute = MagicMock(return_value=None)
    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)
    return mock_engine


def _mock_db_no_user() -> MagicMock:
    db = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value.first.return_value = None
    db.query.return_value = query_mock
    return db


@pytest.fixture
def client_with_mocks() -> Generator[TestClient, None, None]:
    """TestClient with all external dependencies mocked."""
    from app.main import app

    mock_engine = _mock_engine_connect()
    mock_db = MagicMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__enter__.return_value = mock_db
    mock_session_ctx.__exit__.return_value = False

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


def test_health_endpoint_has_security_headers(client_with_mocks: TestClient) -> None:
    """The /health endpoint must carry standard security headers."""
    response = client_with_mocks.get("/health")
    assert response.status_code == 200

    headers = {k.lower(): v for k, v in response.headers.items()}

    # X-Content-Type-Options
    assert "x-content-type-options" in headers, "Missing X-Content-Type-Options header"
    assert headers["x-content-type-options"].lower() == "nosniff"

    # X-Frame-Options or Content-Security-Policy (secure lib may use CSP instead)
    has_frame_protection = "x-frame-options" in headers or "content-security-policy" in headers
    assert has_frame_protection, "Missing X-Frame-Options or Content-Security-Policy header"


def test_auth_login_has_security_headers(client_with_mocks: TestClient) -> None:
    """Even error responses from /auth/login must carry security headers."""
    from app.main import app

    db = _mock_db_no_user()

    def _override() -> Generator[MagicMock, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        response = client_with_mocks.post(
            "/auth/login",
            headers={"origin": "http://localhost:3000"},
            json={"email": "nobody@example.com", "password": "doesnotexist123!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    headers = {k.lower(): v for k, v in response.headers.items()}
    assert "x-content-type-options" in headers


def test_body_limit_honors_configured_max_upload_size(client_with_mocks: TestClient) -> None:
    """Request body middleware must reject bodies above configured max, without extra slack."""
    from app.main import settings

    original_limit = settings.max_upload_size_mb
    settings.max_upload_size_mb = 0
    try:
        response = client_with_mocks.post(
            "/auth/login",
            content=b"x",
            headers={
                "content-type": "application/octet-stream",
                "origin": "http://localhost:3000",
            },
        )
    finally:
        settings.max_upload_size_mb = original_limit

    assert response.status_code == 413


@pytest.mark.anyio
async def test_chunked_body_limit_rejects_oversized_chunked_requests() -> None:
    from app.main import limit_body_size, settings

    original_limit = settings.max_upload_size_mb
    settings.max_upload_size_mb = 0
    chunks = [b"x"]

    async def receive() -> dict[str, object]:
        if chunks:
            chunk = chunks.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/auth/login",
        "headers": [(b"transfer-encoding", b"chunked")],
    }
    request = Request(scope, receive)

    async def call_next(_request: Request) -> Response:
        return Response(status_code=200)

    try:
        response = await limit_body_size(request, call_next)
    finally:
        settings.max_upload_size_mb = original_limit

    assert response.status_code == 413


@pytest.mark.anyio
async def test_chunked_body_limit_rewinds_body_for_downstream_handlers() -> None:
    from app.main import limit_body_size, settings

    original_limit = settings.max_upload_size_mb
    settings.max_upload_size_mb = 1
    chunks = [b"abc", b"def"]
    seen: dict[str, bytes] = {}

    async def receive() -> dict[str, object]:
        if chunks:
            chunk = chunks.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/auth/login",
        "headers": [(b"transfer-encoding", b"chunked")],
    }
    request = Request(scope, receive)

    async def call_next(next_request: Request) -> Response:
        seen["body"] = await next_request.body()
        return Response(status_code=200)

    try:
        response = await limit_body_size(request, call_next)
    finally:
        settings.max_upload_size_mb = original_limit

    assert response.status_code == 200
    assert seen["body"] == b"abcdef"
