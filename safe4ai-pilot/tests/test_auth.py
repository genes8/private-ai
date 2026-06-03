"""Tests for JWT auth, login/logout endpoints, and RBAC."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.middleware import decode_token, encode_token
from app.db import get_db
from app.db.models import User, UserRole
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    *,
    user_id: str = "user-1",
    email: str = "alice@example.com",
    role: UserRole = UserRole.pilot_user,
    is_active: bool = True,
    failed_login_count: int = 0,
    locked_until: datetime | None = None,
    password_hash: str = "",
) -> User:
    user = User()
    setattr(user, "id", user_id)
    setattr(user, "email", email)
    setattr(user, "role", role)
    setattr(user, "is_active", is_active)
    setattr(user, "failed_login_count", failed_login_count)
    setattr(user, "locked_until", locked_until)
    setattr(user, "password_hash", password_hash)
    return user


def _mock_db_with_user(user: User | None) -> MagicMock:
    """Return a mock Session that returns *user* for any query."""
    db = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value.first.return_value = user
    db.query.return_value = query_mock
    db.get.return_value = user
    return db


def _override_get_db(db: MagicMock) -> Callable[[], Generator[MagicMock, None, None]]:
    """Return a FastAPI dependency override that yields the mock db."""

    def _override() -> Generator[MagicMock, None, None]:
        yield db

    return _override


_ALLOWED_ORIGIN = "http://localhost:3000"


def _config_row(key: str, value: object) -> SimpleNamespace:
    return SimpleNamespace(key=key, value=value)


def _oidc_rows(**overrides: object) -> list[SimpleNamespace]:
    values: dict[str, object] = {
        "oidc_enabled": True,
        "oidc_issuer_url": "https://idp.example.com",
        "oidc_client_id": "safe4ai",
        "oidc_client_secret": "secret-value",
        "oidc_redirect_uri": "http://localhost:8000/auth/sso/callback",
        "oidc_allowed_domains": ["example.com"],
        "oidc_auto_provision": False,
    }
    values.update(overrides)
    return [_config_row(key, value) for key, value in values.items()]


# ---------------------------------------------------------------------------
# test_login_success
# ---------------------------------------------------------------------------


def _get_csrf(client: TestClient) -> str:
    """Fetch a pre-login CSRF token and store it in the client's cookie jar."""
    r = client.get("/auth/csrf")
    assert r.status_code == 200
    return r.json()["csrf_token"]


def test_login_success(test_client: TestClient) -> None:
    from app.auth.middleware import hash_password

    hashed = hash_password("SuperSecret123!")
    user = _make_user(password_hash=hashed)
    db = _mock_db_with_user(user)

    csrf_token = _get_csrf(test_client)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            headers={"origin": _ALLOWED_ORIGIN, "X-CSRF-Token": csrf_token},
            json={"email": "alice@example.com", "password": "SuperSecret123!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == {"message": "logged in"}
    assert "access_token" in response.cookies


def test_sso_status_reports_configured_oidc(test_client: TestClient) -> None:
    db = _mock_db_with_user(None)
    db.query.return_value.all.return_value = _oidc_rows()
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.get("/auth/sso/status")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["configured"] is True
    assert body["loginUrl"] == "/auth/sso/start"
    assert "secret" not in str(body).lower()


def test_password_login_blocked_when_sso_only_and_oidc_configured(
    test_client: TestClient,
) -> None:
    from app.auth.middleware import hash_password

    hashed = hash_password("SuperSecret123!")
    user = _make_user(password_hash=hashed)
    db = _mock_db_with_user(user)
    db.query.return_value.all.return_value = _oidc_rows(sso_only=True)

    csrf_token = _get_csrf(test_client)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            headers={"origin": _ALLOWED_ORIGIN, "X-CSRF-Token": csrf_token},
            json={"email": "alice@example.com", "password": "SuperSecret123!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert "sso" in response.json()["detail"].lower()


def test_sso_callback_sets_session_for_existing_user(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_userinfo(*args: object, **kwargs: object) -> dict[str, object]:
        return {"email": "alice@example.com", "email_verified": True}

    user = _make_user(email="alice@example.com")
    db = _mock_db_with_user(user)
    db.query.return_value.all.return_value = _oidc_rows()
    monkeypatch.setattr("app.auth.router.exchange_code_for_userinfo", _fake_userinfo)

    test_client.cookies.set("oidc_state", "state-123")
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.get(
            "/auth/sso/callback?code=code-123&state=state-123",
            follow_redirects=False,
        )
    finally:
        test_client.cookies.clear()
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code in {302, 307}
    assert "access_token" in response.cookies
    assert user.failed_login_count == 0


# ---------------------------------------------------------------------------
# test_login_wrong_password
# ---------------------------------------------------------------------------


def test_login_wrong_password(test_client: TestClient) -> None:
    from app.auth.middleware import hash_password

    hashed = hash_password("SuperSecret123!")
    user = _make_user(password_hash=hashed)
    db = _mock_db_with_user(user)

    csrf_token = _get_csrf(test_client)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            headers={"origin": _ALLOWED_ORIGIN, "X-CSRF-Token": csrf_token},
            json={"email": "alice@example.com", "password": "WrongPassword999!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]
    assert "access_token" not in response.text


# ---------------------------------------------------------------------------
# test_login_account_locked
# ---------------------------------------------------------------------------


def test_login_account_locked(test_client: TestClient) -> None:
    from app.auth.middleware import hash_password

    hashed = hash_password("SuperSecret123!")
    locked_until = datetime.now(UTC) + timedelta(minutes=10)
    user = _make_user(
        password_hash=hashed,
        failed_login_count=5,
        locked_until=locked_until,
    )
    db = _mock_db_with_user(user)

    csrf_token = _get_csrf(test_client)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            headers={"origin": _ALLOWED_ORIGIN, "X-CSRF-Token": csrf_token},
            json={"email": "alice@example.com", "password": "SuperSecret123!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 429
    assert "locked" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# test_logout_clears_cookie
# ---------------------------------------------------------------------------


def test_logout_clears_cookie(test_client: TestClient) -> None:
    user = _make_user()
    db = _mock_db_with_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    token = encode_token("user-1", "pilot_user")
    csrf_token = "test-csrf-token"
    test_client.cookies.set("access_token", token)
    test_client.cookies.set("csrf_token", csrf_token)
    test_client.headers["X-CSRF-Token"] = csrf_token

    try:
        response = test_client.post("/auth/logout")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    assert response.json() == {"message": "logged out"}
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token" in set_cookie
    assert "csrf_token" in set_cookie
    assert "max-age=0" in set_cookie.lower()
    assert user.token_valid_after is not None


def test_logout_requires_csrf_when_authenticated(test_client: TestClient) -> None:
    user = _make_user()
    db = _mock_db_with_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    token = encode_token("user-1", "pilot_user")
    test_client.cookies.set("access_token", token)

    try:
        response = test_client.post("/auth/logout")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# test_require_role_admin_blocks_pilot
# ---------------------------------------------------------------------------


def test_require_role_admin_blocks_pilot(test_client: TestClient) -> None:
    """A pilot_user token should be refused on an admin-only endpoint."""
    from fastapi import APIRouter, Depends

    from app.auth.middleware import require_role

    pilot_user = _make_user(role=UserRole.pilot_user)
    db = _mock_db_with_user(pilot_user)

    # Register a temporary admin-only route
    temp_router = APIRouter()

    @temp_router.get("/test-admin-only")
    def _admin_only(_user: User = Depends(require_role("admin"))) -> dict[str, str]:
        return {"ok": "yes"}

    app.include_router(temp_router)

    pilot_token = encode_token(str(pilot_user.id), str(pilot_user.role))

    app.dependency_overrides[get_db] = _override_get_db(db)
    test_client.cookies.set("access_token", pilot_token)
    try:
        response = test_client.get("/test-admin-only")
    finally:
        test_client.cookies.clear()
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# test_token_encode_decode
# ---------------------------------------------------------------------------


def test_token_encode_decode() -> None:
    token = encode_token("user-42", "admin")
    assert isinstance(token, str)
    payload = decode_token(token)
    assert payload["sub"] == "user-42"
    assert payload["role"] == "admin"


def test_decode_token_rejects_tampered() -> None:
    import jwt

    token = encode_token("user-42", "admin")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(jwt.PyJWTError):
        decode_token(tampered)


def test_login_short_password_rejected(test_client: TestClient) -> None:
    """Passwords shorter than 12 chars must be rejected server-side."""
    db = _mock_db_with_user(None)
    csrf_token = _get_csrf(test_client)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            headers={"origin": _ALLOWED_ORIGIN, "X-CSRF-Token": csrf_token},
            json={"email": "alice@example.com", "password": "short"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


def test_get_csrf_token_sets_cookie(test_client: TestClient) -> None:
    response = test_client.get("/auth/csrf")
    assert response.status_code == 200
    data = response.json()
    assert "csrf_token" in data
    assert len(data["csrf_token"]) >= 32
    assert "csrf_token" in response.cookies


def test_login_without_csrf_token_is_rejected(test_client: TestClient) -> None:
    response = test_client.post(
        "/auth/login",
        headers={"origin": _ALLOWED_ORIGIN},
        json={"email": "alice@example.com", "password": "SuperSecret123!"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_login_rejects_cross_origin_request(test_client: TestClient) -> None:
    db = _mock_db_with_user(None)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            headers={"origin": "https://evil.example"},
            json={"email": "alice@example.com", "password": "SuperSecret123!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_login_rejects_missing_origin_header(test_client: TestClient) -> None:
    db = _mock_db_with_user(None)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "SuperSecret123!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_expired_lockout_is_cleared_before_next_failed_attempt(test_client: TestClient) -> None:
    from app.auth.middleware import hash_password

    hashed = hash_password("SuperSecret123!")
    expired_lock = datetime.now(UTC) - timedelta(minutes=1)
    user = _make_user(
        password_hash=hashed,
        failed_login_count=5,
        locked_until=expired_lock,
    )
    db = _mock_db_with_user(user)

    csrf_token = _get_csrf(test_client)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            headers={"origin": _ALLOWED_ORIGIN, "X-CSRF-Token": csrf_token},
            json={"email": "alice@example.com", "password": "WrongPassword999!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
    assert user.failed_login_count == 1
    assert user.locked_until is None


def test_revoked_token_is_rejected_on_next_request(test_client: TestClient) -> None:
    user = _make_user()
    token = encode_token("user-1", "pilot_user")
    user.token_valid_after = datetime.now(UTC)
    db = _mock_db_with_user(user)

    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        test_client.cookies.set("access_token", token)
        test_client.cookies.set("csrf_token", "test-csrf-token")
        test_client.headers["X-CSRF-Token"] = "test-csrf-token"
        response = test_client.post("/auth/logout")
    finally:
        test_client.cookies.clear()
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
