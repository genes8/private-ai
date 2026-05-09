"""Integration tests for observability API routes using FastAPI TestClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def obs_client() -> TestClient:
    """TestClient with the observability router and all external dependencies mocked."""
    from fastapi import FastAPI

    from app.api.observability_routes import router as obs_router
    from app.auth.middleware import get_current_user
    from app.db import get_db
    from app.db.models import User, UserRole

    mock_db = MagicMock()

    def override_get_db() -> MagicMock:
        return mock_db

    def override_get_current_user() -> User:
        admin = User()
        setattr(admin, "id", "admin-1")
        setattr(admin, "role", UserRole.admin)
        setattr(admin, "is_active", True)
        return admin

    test_app = FastAPI()
    test_app.include_router(obs_router)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(test_app)


class TestSubmitFeedback:
    def test_submit_feedback_positive(self, obs_client: TestClient) -> None:
        with (
            patch("app.api.observability_routes.FeedbackStore") as MockStore,
        ):
            mock_instance = MagicMock()
            mock_instance.store.return_value = "feedback-uuid-123"
            MockStore.return_value = mock_instance

            resp = obs_client.post(
                "/feedback",
                json={
                    "session_id": "sess-1",
                    "trace_id": "trace-1",
                    "rating": "positive",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["id"] == "feedback-uuid-123"

    def test_submit_feedback_negative_with_comment(self, obs_client: TestClient) -> None:
        with patch("app.api.observability_routes.FeedbackStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.store.return_value = "feedback-uuid-456"
            MockStore.return_value = mock_instance

            resp = obs_client.post(
                "/feedback",
                json={
                    "session_id": "sess-2",
                    "trace_id": "trace-2",
                    "rating": "negative",
                    "comment": "Not helpful",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["id"] == "feedback-uuid-456"

    def test_submit_feedback_invalid_rating(self, obs_client: TestClient) -> None:
        resp = obs_client.post(
            "/feedback",
            json={
                "session_id": "sess-3",
                "trace_id": "trace-3",
                "rating": "invalid_rating",
            },
        )
        assert resp.status_code == 422

    def test_submit_feedback_missing_required_field(self, obs_client: TestClient) -> None:
        resp = obs_client.post(
            "/feedback",
            json={"session_id": "sess-4"},  # missing trace_id and rating
        )
        assert resp.status_code == 422


class TestCostStats:
    def test_cost_stats_returns_dict(self, obs_client: TestClient) -> None:
        expected = {"total_cost_usd": 0.042, "runs_count": 10, "by_day": []}

        with patch("app.api.observability_routes.CostTracker") as MockTracker:
            mock_instance = MagicMock()
            mock_instance.get_stats.return_value = expected
            MockTracker.return_value = mock_instance

            resp = obs_client.get("/admin/stats/cost")

        assert resp.status_code == 200
        body = resp.json()
        assert "total_cost_usd" in body
        assert body["total_cost_usd"] == pytest.approx(0.042)
        assert body["runs_count"] == 10

    def test_cost_stats_custom_days(self, obs_client: TestClient) -> None:
        with patch("app.api.observability_routes.CostTracker") as MockTracker:
            mock_instance = MagicMock()
            mock_instance.get_stats.return_value = {
                "total_cost_usd": 0.0,
                "runs_count": 0,
                "by_day": [],
            }
            MockTracker.return_value = mock_instance

            resp = obs_client.get("/admin/stats/cost?days=7")

        assert resp.status_code == 200
        mock_instance.get_stats.assert_called_once()
        call_kwargs = mock_instance.get_stats.call_args
        assert call_kwargs[1].get("days") == 7 or call_kwargs[0][1] == 7


class TestListFeedback:
    def test_list_feedback_returns_list(self, obs_client: TestClient) -> None:
        fake_feedback = [
            {
                "id": "f1",
                "user_id": "u1",
                "session_id": "s1",
                "trace_id": "t1",
                "rating": "positive",
                "comment": None,
                "created_at": "2026-05-01T10:00:00+00:00",
            }
        ]
        with patch("app.api.observability_routes.FeedbackStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.list_for_admin.return_value = fake_feedback
            MockStore.return_value = mock_instance

            resp = obs_client.get("/admin/feedback")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["id"] == "f1"
