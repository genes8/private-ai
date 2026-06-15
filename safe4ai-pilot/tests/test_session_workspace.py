"""Session/workspace binding invariant (A5).

A chat session is immutable to the workspace it was created in: replaying its id
under a different active workspace is a 409, and session list/messages are scoped
to the active workspace.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import User, UserRole
from app.main import app

SESSION_ID = "11111111-2222-3333-4444-555555555555"


def _user() -> User:
    u = User()
    setattr(u, "id", "u1")
    setattr(u, "email", "t@x.local")
    setattr(u, "role", UserRole.pilot_user)
    setattr(u, "is_active", True)
    setattr(u, "failed_login_count", 0)
    setattr(u, "locked_until", None)
    return u


def _session_row(workspace_id: str) -> MagicMock:
    row = MagicMock()
    row.id = SESSION_ID
    row.user_id = "u1"
    row.workspace_id = workspace_id
    row.updated_at = None
    row.state_json = {"messages": [{"role": "user", "content": "hi"}]}
    return row


@pytest.fixture
def client_with_session() -> Generator[tuple[TestClient, MagicMock], None, None]:
    """Authed client whose DB returns a session bound to workspace 'ws-a'."""
    from app.auth.middleware import encode_token

    user = _user()
    row = _session_row("ws-a")
    db = MagicMock()
    db.get.side_effect = lambda model, pk: user if model is User else row

    def _override() -> Generator[MagicMock, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)
    client.cookies.set("access_token", encode_token("u1", "pilot_user"))
    client.cookies.set("csrf_token", "csrf")
    client.headers["X-CSRF-Token"] = "csrf"
    # The user belongs to both workspaces, so resolution succeeds for either.
    with (
        patch("app.services.workspace_service.assert_member", return_value=None),
        patch(
            "app.services.workspace_service.list_workspace_ids_for_user",
            return_value=["ws-a", "ws-b"],
        ),
    ):
        yield client, db
    app.dependency_overrides.clear()


def test_replaying_session_in_other_workspace_is_409(
    client_with_session: tuple[TestClient, MagicMock],
) -> None:
    client, _db = client_with_session
    app.state.graph = AsyncMock()  # type: ignore[union-attr]

    # Session is bound to ws-a; send it with active workspace ws-b.
    response = client.post(
        "/chat",
        json={"question": "hello", "session_id": SESSION_ID},
        headers={"X-Workspace-Id": "ws-b"},
    )
    assert response.status_code == 409


def test_session_messages_wrong_workspace_is_404(
    client_with_session: tuple[TestClient, MagicMock],
) -> None:
    client, _db = client_with_session
    # Session bound to ws-a; request it under ws-b.
    response = client.get(
        f"/chat/sessions/{SESSION_ID}/messages",
        headers={"X-Workspace-Id": "ws-b"},
    )
    assert response.status_code == 404


def test_session_messages_correct_workspace_ok(
    client_with_session: tuple[TestClient, MagicMock],
) -> None:
    client, _db = client_with_session
    response = client.get(
        f"/chat/sessions/{SESSION_ID}/messages",
        headers={"X-Workspace-Id": "ws-a"},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == SESSION_ID
