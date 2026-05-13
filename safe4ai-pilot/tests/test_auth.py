"""Tests for JWT auth, login/logout endpoints, and RBAC."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
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


# ---------------------------------------------------------------------------
# test_login_success
# ---------------------------------------------------------------------------


def test_login_success(test_client: TestClient) -> None:
    from app.auth.middleware import hash_password

    hashed = hash_password("SuperSecret123!")
    user = _make_user(password_hash=hashed)
    db = _mock_db_with_user(user)

    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "SuperSecret123!"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == {"message": "logged in"}
    assert "access_token" in response.cookies


# ---------------------------------------------------------------------------
# test_login_wrong_password
# ---------------------------------------------------------------------------


def test_login_wrong_password(test_client: TestClient) -> None:
    from app.auth.middleware import hash_password

    hashed = hash_password("SuperSecret123!")
    user = _make_user(password_hash=hashed)
    db = _mock_db_with_user(user)

    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
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
        failed_login_count=20,
        locked_until=locked_until,
    )
    db = _mock_db_with_user(user)

    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        response = test_client.post(
            "/auth/login",
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
    token = encode_token("user-1", "pilot_user")
    csrf_token = "test-csrf-token"
    test_client.cookies.set("access_token", token)
    test_client.cookies.set("csrf_token", csrf_token)
    test_client.headers["X-CSRF-Token"] = csrf_token

    response = test_client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "logged out"}
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token" in set_cookie
    assert "csrf_token" in set_cookie
    assert "max-age=0" in set_cookie.lower()


def test_logout_requires_csrf_when_authenticated(test_client: TestClient) -> None:
    token = encode_token("user-1", "pilot_user")
    test_client.cookies.set("access_token", token)

    response = test_client.post("/auth/logout")

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
    response = test_client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "short"},
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]
