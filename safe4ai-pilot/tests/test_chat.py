"""Tests for POST /chat endpoint."""

from __future__ import annotations

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.db.models import User, UserRole
from app.main import app
from app.models import Citation, Message, PrivateAIState


def _make_user(
    user_id: str = "u1",
    role: UserRole = UserRole.pilot_user,
    is_active: bool = True,
) -> User:
    u = User()
    setattr(u, "id", user_id)
    setattr(u, "email", "tester@example.com")
    setattr(u, "role", role)
    setattr(u, "is_active", is_active)
    setattr(u, "failed_login_count", 0)
    setattr(u, "locked_until", None)
    return u


def _make_db(user: User | None) -> MagicMock:
    db = MagicMock()
    db.get.return_value = user
    return db


def _db_override(db: MagicMock) -> Callable[[], Generator[MagicMock, None, None]]:
    def _inner() -> Generator[MagicMock, None, None]:
        yield db

    return _inner


def _make_final_state(session_id: str = "sess-1", user_id: str = "u1") -> PrivateAIState:
    return PrivateAIState(
        session_id=session_id,
        user_id=user_id,
        messages=[Message(role="user", content="Test question")],
        current_step="respond",
        status="completed",
        draft_answer="The answer is 42.",
        citations=[
            Citation(filename="doc.pdf", page_number=1, excerpt="The answer is 42.", score=0.9)
        ],
        trace_id="trace-abc",
    )


@pytest.fixture
def authed_client() -> Generator[TestClient, None, None]:
    """TestClient with a valid JWT cookie and mocked DB."""
    from app.auth.middleware import encode_token

    user = _make_user()
    db = _make_db(user)

    app.dependency_overrides[get_db] = _db_override(db)
    token = encode_token("u1", "pilot_user")
    client = TestClient(app)
    csrf_token = "test-csrf-token"
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf_token)
    client.headers["X-CSRF-Token"] = csrf_token
    yield client
    app.dependency_overrides.clear()


def test_chat_returns_answer(authed_client: TestClient) -> None:
    session_id = "sess-1"
    final_state = _make_final_state(session_id=session_id)

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=final_state)

    new_session = "app.services.conversation.ConversationManager.new_session"
    load_session = "app.services.conversation.ConversationManager.load_session"
    save_session = "app.services.conversation.ConversationManager.save_session"
    init_state = PrivateAIState(session_id=session_id, user_id="u1")
    with patch(new_session, return_value=session_id):
        with patch(load_session, return_value=init_state):
            with patch(save_session):
                authed_client.app.state.graph = mock_graph  # type: ignore[union-attr]
                response = authed_client.post("/chat", json={"question": "What is the answer?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "The answer is 42."
    assert data["session_id"] == session_id
    assert len(data["citations"]) == 1
    assert data["citations"][0]["filename"] == "doc.pdf"


def test_chat_empty_question_rejected(authed_client: TestClient) -> None:
    authed_client.app.state.graph = AsyncMock()  # type: ignore[union-attr]
    response = authed_client.post("/chat", json={"question": "   "})
    assert response.status_code == 422


def test_chat_no_auth_returns_401() -> None:
    client = TestClient(app)
    response = client.post("/chat", json={"question": "hello"})
    assert response.status_code == 401


def test_chat_graph_not_initialized(authed_client: TestClient) -> None:
    session_id = "sess-2"
    new_session = "app.services.conversation.ConversationManager.new_session"
    load_session = "app.services.conversation.ConversationManager.load_session"
    init_state = PrivateAIState(session_id=session_id, user_id="u1")
    with patch(new_session, return_value=session_id):
        with patch(load_session, return_value=init_state):
            authed_client.app.state.graph = None  # type: ignore[union-attr]
            response = authed_client.post("/chat", json={"question": "hello"})

    assert response.status_code == 503


def test_chat_rejects_session_owned_by_another_user(authed_client: TestClient) -> None:
    authed_client.app.state.graph = AsyncMock()  # type: ignore[union-attr]
    foreign_session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    foreign_state = PrivateAIState(session_id=foreign_session_id, user_id="someone-else")

    with patch(
        "app.services.conversation.ConversationManager.load_session",
        return_value=foreign_state,
    ):
        response = authed_client.post(
            "/chat",
            json={"question": "hello", "session_id": foreign_session_id},
        )

    assert response.status_code == 404


def test_chat_rejects_when_daily_cost_ceiling_reached(authed_client: TestClient) -> None:
    with patch(
        "app.services.app_config_store.load_app_config",
        return_value={"daily_ceiling_usd": 10, "monthly_ceiling_usd": 500},
    ), patch(
        "app.api.chat_routes.CostTracker.get_stats",
        return_value={"total_cost_usd": 10.0, "runs_count": 1, "by_day": []},
    ):
        response = authed_client.post("/chat", json={"question": "What is the answer?"})

    assert response.status_code == 429
    assert "Daily cost ceiling reached" in response.json()["detail"]


def test_chat_stream_rejects_when_monthly_cost_ceiling_reached(authed_client: TestClient) -> None:
    with patch(
        "app.services.app_config_store.load_app_config",
        return_value={"daily_ceiling_usd": 50, "monthly_ceiling_usd": 100},
    ), patch(
        "app.api.chat_routes.CostTracker.get_stats",
        side_effect=[
            {"total_cost_usd": 10.0, "runs_count": 1, "by_day": []},
            {"total_cost_usd": 100.0, "runs_count": 20, "by_day": []},
        ],
    ):
        response = authed_client.post("/chat/stream", json={"question": "What is the answer?"})

    assert response.status_code == 429
    assert "Monthly cost ceiling reached" in response.json()["detail"]


def test_chat_rejects_when_projected_request_cost_exceeds_daily_ceiling(
    authed_client: TestClient,
) -> None:
    with patch(
        "app.services.app_config_store.load_app_config",
        return_value={"daily_ceiling_usd": 1.0, "monthly_ceiling_usd": 500},
    ), patch(
        "app.api.chat_routes.CostTracker.get_stats",
        side_effect=[
            {"total_cost_usd": 0.95, "runs_count": 1, "by_day": []},
            {"total_cost_usd": 10.0, "runs_count": 1, "by_day": []},
        ],
    ), patch(
        "app.api.chat_routes.estimate_tokens",
        side_effect=[40, 40],
    ), patch("app.api.chat_routes.settings.cost_per_1k_tokens", 1.0):
        response = authed_client.post("/chat", json={"question": "Will this fit?"})

    assert response.status_code == 429
    assert "Projected request would exceed daily cost ceiling" in response.json()["detail"]


def test_chat_recovers_from_corrupted_session_state(authed_client: TestClient) -> None:
    final_state = _make_final_state(session_id="sess-new")

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=final_state)

    old_session_id = "11111111-2222-3333-4444-555555555555"
    with patch(
        "app.services.conversation.ConversationManager.load_session",
        side_effect=[ValueError("Invalid session state"), PrivateAIState(session_id="sess-new", user_id="u1")],
    ), patch(
        "app.services.conversation.ConversationManager.new_session",
        return_value="sess-new",
    ), patch(
        "app.services.conversation.ConversationManager.save_session",
    ):
        authed_client.app.state.graph = mock_graph  # type: ignore[union-attr]
        response = authed_client.post(
            "/chat",
            json={"question": "Recover this", "session_id": old_session_id},
        )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sess-new"
