"""Security audit test harness — validates all 10 fixes from audit-code-report.md.

F-01: CL/TE desync rejection
F-02: Chat body size bypass removed
F-03: Port binding (checked via docker-compose parse)
F-04: SSRF protection on provider URLs
F-05: Safe body replay via _body (no _receive monkey-patch)
F-06: Health endpoint info masking
F-07: SSE error message sanitization
F-08: nginx header hardening (checked via config parse)
F-09: Default credential enforcement in production mode
F-10: CSRF required for all unsafe methods
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def client_with_health_mocks() -> Generator[TestClient, None, None]:
    from app.main import app

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute = MagicMock(return_value=None)
    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__enter__.return_value = MagicMock()
    mock_session_ctx.__exit__.return_value = False

    async def mock_get(url: str, **_kw: object) -> MagicMock:
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


# ===================================================================
# F-01: CL/TE desync — reject requests with both headers
# ===================================================================


class TestF01_CL_TE_Desync:
    """Requests carrying both Content-Length and Transfer-Encoding must be rejected."""

    @pytest.mark.anyio
    async def test_both_cl_and_te_returns_400(self) -> None:
        from app.main import limit_body_size, settings

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/some/path",
            "headers": [
                (b"content-length", b"10"),
                (b"transfer-encoding", b"chunked"),
            ],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"0123456789", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await limit_body_size(request, call_next)
        assert response.status_code == 400
        assert b"Ambiguous" in response.body

    @pytest.mark.anyio
    async def test_cl_only_passes(self) -> None:
        from app.main import limit_body_size, settings

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"content-length", b"5")],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"hello", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await limit_body_size(request, call_next)
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_te_only_passes(self) -> None:
        from app.main import limit_body_size, settings

        original = settings.max_upload_size_mb
        settings.max_upload_size_mb = 1
        chunks = [b"hello"]

        async def receive() -> dict[str, object]:
            if chunks:
                c = chunks.pop(0)
                return {"type": "http.request", "body": c, "more_body": bool(chunks)}
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"transfer-encoding", b"chunked")],
        }
        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        try:
            response = await limit_body_size(request, call_next)
        finally:
            settings.max_upload_size_mb = original
        assert response.status_code == 200


# ===================================================================
# F-02: Chat body size bypass removed
# ===================================================================


class TestF02_ChatBodySizeBypass:
    """Chunked requests to /chat and /chat/stream must now be size-checked."""

    @pytest.mark.anyio
    async def test_chat_chunked_oversized_rejected(self) -> None:
        from app.main import limit_body_size, settings

        original = settings.max_upload_size_mb
        settings.max_upload_size_mb = 0  # 0 bytes max
        chunks = [b"x"]

        async def receive() -> dict[str, object]:
            if chunks:
                c = chunks.pop(0)
                return {"type": "http.request", "body": c, "more_body": bool(chunks)}
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [(b"transfer-encoding", b"chunked")],
        }
        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        try:
            response = await limit_body_size(request, call_next)
        finally:
            settings.max_upload_size_mb = original
        assert response.status_code == 413

    @pytest.mark.anyio
    async def test_chat_stream_chunked_oversized_rejected(self) -> None:
        from app.main import limit_body_size, settings

        original = settings.max_upload_size_mb
        settings.max_upload_size_mb = 0
        chunks = [b"x"]

        async def receive() -> dict[str, object]:
            if chunks:
                c = chunks.pop(0)
                return {"type": "http.request", "body": c, "more_body": bool(chunks)}
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/stream",
            "headers": [(b"transfer-encoding", b"chunked")],
        }
        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        try:
            response = await limit_body_size(request, call_next)
        finally:
            settings.max_upload_size_mb = original
        assert response.status_code == 413


# ===================================================================
# F-03: Port 8000 bound to localhost in docker-compose
# ===================================================================


class TestF03_PortExposure:
    """docker-compose.yml must bind port 8000 to 127.0.0.1 only."""

    def test_docker_compose_port_is_localhost_only(self) -> None:
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        content = compose_path.read_text()
        assert "127.0.0.1:8000:8000" in content, (
            "Port 8000 must be bound to 127.0.0.1 to prevent direct external access"
        )
        # Must NOT contain bare "8000:8000" without localhost binding
        lines = content.splitlines()
        for line in lines:
            stripped = line.strip().strip("-").strip().strip('"').strip("'")
            if stripped == "8000:8000":
                pytest.fail("Found bare '8000:8000' port mapping without 127.0.0.1 binding")


# ===================================================================
# F-04: SSRF protection on provider URLs
# ===================================================================


class TestF04_SSRF:
    """Provider URL validator must block private/reserved IP ranges."""

    def test_blocks_localhost(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("http://127.0.0.1:8080/v1")
        assert exc_info.value.status_code == 422
        assert "private" in exc_info.value.detail.lower()

    def test_blocks_metadata_endpoint(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("http://169.254.169.254/latest/meta-data")
        assert exc_info.value.status_code == 422

    def test_blocks_private_10_range(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("http://10.0.0.1:11434")
        assert exc_info.value.status_code == 422

    def test_blocks_private_172_range(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("http://172.16.0.1:8000")
        assert exc_info.value.status_code == 422

    def test_blocks_private_192_range(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("http://192.168.1.1:8000")
        assert exc_info.value.status_code == 422

    def test_blocks_file_scheme(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("file:///etc/passwd")
        assert exc_info.value.status_code == 422
        assert "scheme" in exc_info.value.detail.lower()

    def test_blocks_ftp_scheme(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("ftp://evil.example.com")
        assert exc_info.value.status_code == 422

    def test_blocks_empty_hostname(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with pytest.raises(HTTPException) as exc_info:
            validate_provider_url("http://")
        assert exc_info.value.status_code == 422
        assert "hostname" in exc_info.value.detail.lower()

    def test_allows_public_url(self) -> None:
        from app.security.url_validator import validate_provider_url

        # Mock DNS resolution to return a public IP
        fake_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 0))]
        with patch("app.security.url_validator.socket.getaddrinfo", return_value=fake_addrinfo):
            result = validate_provider_url("https://api.openai.com/v1")
        assert result == "https://api.openai.com/v1"

    def test_strips_trailing_slash(self) -> None:
        from app.security.url_validator import validate_provider_url

        fake_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 0))]
        with patch("app.security.url_validator.socket.getaddrinfo", return_value=fake_addrinfo):
            result = validate_provider_url("https://api.example.com/v1/")
        assert result == "https://api.example.com/v1"

    def test_blocks_ipv6_loopback(self) -> None:
        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        fake_addrinfo = [(10, 1, 6, "", ("::1", 0, 0, 0))]
        with patch("app.security.url_validator.socket.getaddrinfo", return_value=fake_addrinfo):
            with pytest.raises(HTTPException) as exc_info:
                validate_provider_url("http://ipv6-loopback.example.com:8080")
            assert exc_info.value.status_code == 422

    def test_blocks_unresolvable_host(self) -> None:
        import socket as _socket

        from fastapi import HTTPException

        from app.security.url_validator import validate_provider_url

        with patch(
            "app.security.url_validator.socket.getaddrinfo",
            side_effect=_socket.gaierror("Name resolution failed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                validate_provider_url("http://nonexistent.internal.corp")
            assert exc_info.value.status_code == 422
            assert "resolve" in exc_info.value.detail.lower()


# ===================================================================
# F-05: Safe body replay (no _receive monkey-patch)
# ===================================================================


class TestF05_SafeBodyReplay:
    """Chunked body replay must use _body, not _receive/_stream_consumed."""

    @pytest.mark.anyio
    async def test_replayed_body_accessible_downstream(self) -> None:
        from app.main import limit_body_size, settings

        original = settings.max_upload_size_mb
        settings.max_upload_size_mb = 1
        chunks = [b"abc", b"def"]
        seen: dict[str, bytes] = {}

        async def receive() -> dict[str, object]:
            if chunks:
                c = chunks.pop(0)
                return {"type": "http.request", "body": c, "more_body": bool(chunks)}
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"transfer-encoding", b"chunked")],
        }
        request = Request(scope, receive)

        async def call_next(r: Request) -> Response:
            seen["body"] = await r.body()
            return Response(status_code=200)

        try:
            response = await limit_body_size(request, call_next)
        finally:
            settings.max_upload_size_mb = original

        assert response.status_code == 200
        assert seen["body"] == b"abcdef"

    @pytest.mark.anyio
    async def test_body_set_via_body_attr_not_receive(self) -> None:
        """After chunked replay, _body must be set directly."""
        from app.main import limit_body_size, settings

        original = settings.max_upload_size_mb
        settings.max_upload_size_mb = 1
        chunks = [b"test"]

        async def receive() -> dict[str, object]:
            if chunks:
                c = chunks.pop(0)
                return {"type": "http.request", "body": c, "more_body": bool(chunks)}
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"transfer-encoding", b"chunked")],
        }
        request = Request(scope, receive)

        async def call_next(r: Request) -> Response:
            assert hasattr(r, "_body"), "_body must be set for safe replay"
            assert r._body == b"test"
            return Response(status_code=200)

        try:
            await limit_body_size(request, call_next)
        finally:
            settings.max_upload_size_mb = original


# ===================================================================
# F-06: Health endpoint does not leak internal details
# ===================================================================


class TestF06_HealthInfoLeak:
    """Health checks must return 'ok' or 'error' without exception details."""

    def test_health_postgres_failure_masked(self) -> None:
        from app.main import app

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(side_effect=Exception("connection refused to postgres:5432"))
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect = MagicMock(return_value=mock_conn)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = MagicMock()
        mock_session_ctx.__exit__.return_value = False

        async def mock_get(url: str, **_kw: object) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 200
            return resp

        with (
            patch("app.main.engine", mock_engine),
            patch("app.main.SessionLocal", return_value=mock_session_ctx),
            patch("app.main.load_runtime_config", return_value=MagicMock(provider_type="ollama")),
            patch("httpx.AsyncClient.get", mock_get),
        ):
            client = TestClient(app)
            r = client.get("/health")

        body = r.json()
        assert body["checks"]["postgres"] == "error"
        # Must NOT contain internal connection details
        response_text = str(body)
        assert "5432" not in response_text
        assert "connection refused" not in response_text.lower()

    def test_health_ok_no_extra_details(self) -> None:
        from app.main import app

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.execute = MagicMock(return_value=None)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)

        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = MagicMock()
        mock_session_ctx.__exit__.return_value = False

        async def mock_get(_self: object, url: str, **_kw: object) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 200
            return resp

        with (
            patch("app.main.engine", mock_engine),
            patch("app.main.SessionLocal", return_value=mock_session_ctx),
            patch("app.main.load_runtime_config", return_value=MagicMock(provider_type="ollama")),
            patch("httpx.AsyncClient.get", mock_get),
        ):
            client = TestClient(app)
            r = client.get("/health")

        body = r.json()
        assert body["status"] == "ok"
        for check_value in body["checks"].values():
            assert check_value in {"ok", "error"}, f"Unexpected check value: {check_value}"


# ===================================================================
# F-07: SSE error message sanitization
# ===================================================================


class TestF07_SSEErrorLeak:
    """SSE error events must not contain raw exception text."""

    def test_stream_error_uses_generic_message(self) -> None:
        """Verify that the except block in chat_routes sends 'Pipeline error', not str(exc)."""
        import ast
        source_path = PROJECT_ROOT / "app" / "api" / "chat_routes.py"
        source = source_path.read_text()
        tree = ast.parse(source)

        found_generic = False
        for node in ast.walk(tree):
            # Find string constants containing 'Pipeline error'
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value == "Pipeline error":
                    found_generic = True
                    break
        assert found_generic, "Expected 'Pipeline error' literal in chat_routes.py"

        # Ensure str(exc) is NOT passed to _sse("done", ...)
        assert 'str(exc)' not in source.split('yield _sse("done"')[-1].split('\n')[0], (
            "SSE done event must not contain str(exc) — use a generic message"
        )


# ===================================================================
# F-08: nginx config hardening
# ===================================================================


class TestF08_NginxHardening:
    """nginx.conf must include security hardening directives."""

    def _read_nginx_conf(self) -> str:
        return (PROJECT_ROOT / "frontend" / "nginx.conf").read_text()

    def test_proxy_http_version_11(self) -> None:
        conf = self._read_nginx_conf()
        assert "proxy_http_version 1.1" in conf

    def test_transfer_encoding_scrubbed(self) -> None:
        conf = self._read_nginx_conf()
        assert 'proxy_set_header Transfer-Encoding ""' in conf

    def test_connection_header_scrubbed(self) -> None:
        conf = self._read_nginx_conf()
        assert 'proxy_set_header Connection ""' in conf

    def test_client_max_body_size_set(self) -> None:
        conf = self._read_nginx_conf()
        assert "client_max_body_size" in conf


# ===================================================================
# F-09: Default credential enforcement in production
# ===================================================================


class TestF09_DefaultCredentials:
    """Startup must block when default secrets are used with enforce_https=True."""

    def test_default_secret_key_blocks_in_production(self) -> None:
        from app.startup_migrations import _warn_default_credentials
        from app.config import settings

        original_key = settings.secret_key
        original_https = settings.enforce_https
        settings.secret_key = "68d543ad135bb451bf0e0a26a7fa6cf5151cb1d0b0c6b1366d18f5543a93927e"
        settings.enforce_https = True

        try:
            with pytest.raises(RuntimeError, match="Default SECRET_KEY"):
                _warn_default_credentials()
        finally:
            settings.secret_key = original_key
            settings.enforce_https = original_https

    def test_default_secret_key_warns_in_dev(self) -> None:
        from app.startup_migrations import _warn_default_credentials
        from app.config import settings

        original_key = settings.secret_key
        original_https = settings.enforce_https
        settings.secret_key = "68d543ad135bb451bf0e0a26a7fa6cf5151cb1d0b0c6b1366d18f5543a93927e"
        settings.enforce_https = False

        try:
            # Should NOT raise — just warn
            _warn_default_credentials()
        finally:
            settings.secret_key = original_key
            settings.enforce_https = original_https

    def test_default_pg_password_blocks_in_production(self) -> None:
        from app.startup_migrations import _warn_default_credentials
        from app.config import settings

        original_url = settings.postgres_url
        original_key = settings.secret_key
        original_https = settings.enforce_https
        settings.postgres_url = "postgresql+psycopg2://safe4ai:safe4ai@localhost:5432/safe4ai"
        settings.secret_key = "a_strong_non_default_key_that_is_long_enough_for_validation"
        settings.enforce_https = True

        try:
            with pytest.raises(RuntimeError, match="Default PostgreSQL"):
                _warn_default_credentials()
        finally:
            settings.postgres_url = original_url
            settings.secret_key = original_key
            settings.enforce_https = original_https


# ===================================================================
# F-10: CSRF required for all unsafe methods
# ===================================================================


class TestF10_CSRFGap:
    """CSRF validation must apply to all unsafe methods, even without auth cookies."""

    @pytest.mark.anyio
    async def test_post_without_csrf_rejected(self) -> None:
        from app.main import protect_csrf

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/some/endpoint",
            "headers": [],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await protect_csrf(request, call_next)
        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_put_without_csrf_rejected(self) -> None:
        from app.main import protect_csrf

        scope = {
            "type": "http",
            "method": "PUT",
            "path": "/any/path",
            "headers": [],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await protect_csrf(request, call_next)
        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_delete_without_csrf_rejected(self) -> None:
        from app.main import protect_csrf

        scope = {
            "type": "http",
            "method": "DELETE",
            "path": "/resource/1",
            "headers": [],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await protect_csrf(request, call_next)
        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_get_without_csrf_passes(self) -> None:
        from app.main import protect_csrf

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/any/path",
            "headers": [],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await protect_csrf(request, call_next)
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_matching_csrf_token_passes(self) -> None:
        from app.main import protect_csrf

        token = "secure-random-csrf-token-value"
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/some/endpoint",
            "headers": [
                (b"cookie", f"csrf_token={token}".encode()),
                (b"x-csrf-token", token.encode()),
            ],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await protect_csrf(request, call_next)
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_mismatched_csrf_token_rejected(self) -> None:
        from app.main import protect_csrf

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/some/endpoint",
            "headers": [
                (b"cookie", b"csrf_token=real-token"),
                (b"x-csrf-token", b"wrong-token"),
            ],
        }

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)

        async def call_next(_r: Request) -> Response:
            return Response(status_code=200)

        response = await protect_csrf(request, call_next)
        assert response.status_code == 403
