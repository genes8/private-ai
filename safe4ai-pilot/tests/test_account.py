from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth.middleware import encode_token, hash_password, verify_password
from app.db import get_db
from app.db.models import User, UserRole
from app.main import app


def _make_user(
    *,
    user_id: str = "user-1",
    email: str = "alice@example.com",
    role: UserRole = UserRole.pilot_user,
    password_hash: str | None = None,
    created_at: datetime | None = None,
) -> User:
    user = User()
    user.id = user_id
    user.email = email
    user.role = role
    user.is_active = True
    user.password_hash = password_hash or hash_password("CurrentPass123!")
    user.created_at = created_at or datetime(2026, 5, 25, tzinfo=UTC)
    user.token_valid_after = None
    return user


def _override_get_db(db: MagicMock) -> Callable[[], Generator[MagicMock, None, None]]:
    def _override() -> Generator[MagicMock, None, None]:
        yield db

    return _override


def _authenticated_client(db: MagicMock, user: User) -> TestClient:
    app.dependency_overrides[get_db] = _override_get_db(db)
    client = TestClient(app)
    role = getattr(user.role, "value", user.role)
    client.cookies.set("access_token", encode_token(str(user.id), str(role)))
    client.cookies.set("csrf_token", "csrf-test-token")
    client.headers["X-CSRF-Token"] = "csrf-test-token"
    return client


def _cleanup_overrides() -> None:
    app.dependency_overrides.clear()


def _scalar_query(value: object) -> MagicMock:
    query = MagicMock()
    query.filter.return_value = query
    query.scalar.return_value = value
    return query


def _has_user_scope_filter(filter_args: tuple[object, ...], column_text: str, user_id: str) -> bool:
    for arg in filter_args:
        right = getattr(arg, "right", None)
        if column_text in str(arg) and getattr(right, "value", None) == user_id:
            return True
    return False


def _filter_args(query: MagicMock) -> tuple[object, ...]:
    args: list[object] = []
    for call in query.filter.call_args_list:
        args.extend(call.args)
    return tuple(args)


@contextmanager
def _account_config_patch() -> Iterator[None]:
    try:
        with patch("app.api.account_routes.load_app_config", return_value={}):
            yield
    except (AttributeError, ModuleNotFoundError):
        yield


def test_account_settings_succeeds_for_pilot_user() -> None:
    user = _make_user()
    last_activity_at = datetime(2026, 5, 24, 10, 11, 12, tzinfo=UTC)
    db = MagicMock()
    db.get.return_value = user
    db.query.side_effect = [
        _scalar_query(3),
        _scalar_query(7),
        _scalar_query(2),
        _scalar_query(1),
        _scalar_query(last_activity_at),
        _scalar_query(5),
        _scalar_query(120),
        _scalar_query(0),
        _scalar_query(1),
    ]

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.get("/account/settings")
    finally:
        _cleanup_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["email"] == "alice@example.com"
    assert body["profile"]["role"] == "pilot_user"
    assert body["profile"]["isActive"] is True
    assert body["security"]["sessionHours"] == 24
    assert body["security"]["passwordChangeAllowed"] is True
    assert body["usage"]["questions7d"] == 3
    assert body["usage"]["questions30d"] == 7
    assert body["usage"]["feedbackPositive"] == 2
    assert body["usage"]["feedbackNegative"] == 1
    assert "lastActivityAt" in body["usage"]
    assert "2026-05-24" in body["usage"]["lastActivityAt"]
    assert body["knowledgeBase"]["docCount"] == 5
    assert body["knowledgeBase"]["chunkCount"] == 120


def test_account_settings_filters_usage_by_current_user() -> None:
    user = _make_user(user_id="user-scope")
    db = MagicMock()
    db.get.return_value = user
    scoped_queries = [_scalar_query(0) for _ in range(9)]
    db.query.side_effect = scoped_queries

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.get("/account/settings")
    finally:
        _cleanup_overrides()

    assert response.status_code == 200
    audit_7d_filter_args = _filter_args(scoped_queries[0])
    audit_30d_filter_args = _filter_args(scoped_queries[1])
    positive_feedback_filter_args = _filter_args(scoped_queries[2])
    negative_feedback_filter_args = _filter_args(scoped_queries[3])
    assert _has_user_scope_filter(audit_7d_filter_args, "audit_logs.user_id", user.id)
    assert _has_user_scope_filter(audit_30d_filter_args, "audit_logs.user_id", user.id)
    assert _has_user_scope_filter(positive_feedback_filter_args, "query_feedback.user_id", user.id)
    assert _has_user_scope_filter(negative_feedback_filter_args, "query_feedback.user_id", user.id)


def test_change_password_rejects_wrong_current_password() -> None:
    user = _make_user(password_hash=hash_password("CurrentPass123!"))
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.post(
                "/account/change-password",
                json={"currentPassword": "WrongPass123!", "newPassword": "NewStrongPass123!"},
            )
    finally:
        _cleanup_overrides()

    assert response.status_code == 401
    assert "Current password is incorrect" in response.json()["detail"]
    db.commit.assert_not_called()


def test_change_password_rejects_weak_new_password() -> None:
    user = _make_user(password_hash=hash_password("CurrentPass123!"))
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.post(
                "/account/change-password",
                json={"currentPassword": "CurrentPass123!", "newPassword": "short"},
            )
    finally:
        _cleanup_overrides()

    assert response.status_code == 422
    assert "Password must be at least 12 characters" in response.json()["detail"]
    db.commit.assert_not_called()


def test_change_password_updates_hash_and_invalidates_tokens() -> None:
    old_hash = hash_password("CurrentPass123!")
    user = _make_user(password_hash=old_hash)
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.post(
                "/account/change-password",
                json={"currentPassword": "CurrentPass123!", "newPassword": "NewStrongPass123!"},
            )
    finally:
        _cleanup_overrides()

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed. Please sign in again with your new password."}
    assert user.password_hash != old_hash
    assert verify_password("NewStrongPass123!", user.password_hash)
    assert user.token_valid_after is not None
    assert user.token_valid_after <= datetime.now(UTC)
    db.commit.assert_called_once()


def test_change_password_rejects_old_token_and_accepts_fresh_token() -> None:
    user = _make_user(password_hash=hash_password("CurrentPass123!"))
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.post(
                "/account/change-password",
                json={"currentPassword": "CurrentPass123!", "newPassword": "NewStrongPass123!"},
            )
            old_token_response = client.get("/me")
            role = getattr(user.role, "value", user.role)
            client.cookies.set("access_token", encode_token(str(user.id), str(role)))
            fresh_token_response = client.get("/me")
    finally:
        _cleanup_overrides()

    assert response.status_code == 200
    assert old_token_response.status_code == 401
    assert fresh_token_response.status_code == 200
    assert fresh_token_response.json()["email"] == "alice@example.com"


def test_admin_settings_remains_admin_only_for_pilot_user() -> None:
    user = _make_user(role=UserRole.pilot_user)
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        response = client.get("/settings")
    finally:
        _cleanup_overrides()

    assert response.status_code == 403
