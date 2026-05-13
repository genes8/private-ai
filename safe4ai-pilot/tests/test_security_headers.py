"""Tests for security headers added by the secure middleware."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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

    async def mock_get(url: str, **_kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        return resp

    with (
        patch("app.main.engine", mock_engine),
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
            headers={"content-type": "application/octet-stream"},
        )
    finally:
        settings.max_upload_size_mb = original_limit

    assert response.status_code == 413
