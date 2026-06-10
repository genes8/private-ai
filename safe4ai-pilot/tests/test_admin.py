"""Tests for Phase 3B admin API and Phase 3C runtime hardening (trace_id, max-size)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import (
    IngestionStatus,
    ReviewStatus,
    User,
)
from app.models import Message, PrivateAIState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
from tests.helpers.admin_routes import (
    make_admin_user as _make_admin_user,
)
from tests.helpers.admin_routes import (
    make_document as _make_document,
)
from tests.helpers.admin_routes import (
    make_pilot_user as _make_pilot_user,
)
from tests.helpers.admin_routes import (
    make_test_client as _make_test_client,
)
from tests.helpers.admin_routes import (
    mock_db_with_admin as _mock_db_with_admin,
)


class TestUserManagement:
    def test_list_users_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.order_by.return_value.all.return_value = [admin]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/users")

        assert resp.status_code == 200
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_returns_201(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.filter.return_value.first.return_value = None  # no existing user

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={"email": "new@test.com", "password": "Strongpassword123!",
                      "role": "pilot_user"},
            )

        assert resp.status_code == 201
        assert "id" in resp.json()
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_rejects_short_password(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={"email": "x@test.com", "password": "short", "role": "pilot_user"},
            )

        assert resp.status_code == 422
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_rejects_password_without_required_complexity(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={
                    "email": "x@test.com",
                    "password": "alllowercase123",
                    "role": "pilot_user",
                },
            )

        assert resp.status_code == 422
        assert (
            "Password must include uppercase, lowercase, digit, and special character"
            in resp.json()["detail"]
        )
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_requires_password(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.filter.return_value.first.return_value = None

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={"email": "x@test.com", "role": "pilot_user"},
            )

        assert resp.status_code == 422
        assert resp.json()["detail"] == "Password is required"
        from app.main import app
        app.dependency_overrides.clear()

    def test_deactivate_user_returns_204(self) -> None:
        admin = _make_admin_user()
        target = _make_pilot_user("user-99")
        db = _mock_db_with_admin(admin)
        deleted_user = _make_pilot_user("00000000-0000-0000-0000-000000000001")
        deleted_user.email = "deleted@redacted.local"

        def _get(model: Any, pk: str) -> Any:
            if pk == "admin-1":
                return admin
            if pk == "00000000-0000-0000-0000-000000000001":
                return deleted_user
            return target

        db.get.side_effect = _get

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/users/user-99")

        assert resp.status_code == 204
        assert target.is_active is False
        assert str(target.email).startswith("deactivated+user-99@redacted.local")
        assert target.token_valid_after is not None
        db.commit.assert_called()
        from app.main import app
        app.dependency_overrides.clear()

    def test_cannot_deactivate_own_account(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/users/admin-1")

        assert resp.status_code == 400
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_409_for_duplicate_email(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.filter.return_value.first.return_value = _make_admin_user()

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={"email": "admin@test.com", "password": "Strongpassword123!",
                      "role": "pilot_user"},
            )

        assert resp.status_code == 409
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_rejects_invalid_email_format(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={
                    "email": "bad email@example.com",
                    "password": "strongpassword123",
                    "role": "pilot_user",
                },
            )

        assert resp.status_code == 422
        from app.main import app
        app.dependency_overrides.clear()

    def test_deactivate_user_deletes_agent_runs_for_user_sessions(self) -> None:
        admin = _make_admin_user()
        target = _make_pilot_user("user-77")
        deleted_user = _make_pilot_user("00000000-0000-0000-0000-000000000001")
        deleted_user.email = "deleted@redacted.local"

        db = MagicMock()
        db.get.side_effect = lambda model, pk: {
            "admin-1": admin,
            "user-77": target,
            "00000000-0000-0000-0000-000000000001": deleted_user,
        }.get(pk)

        document_query = MagicMock()
        document_query.filter.return_value.update.return_value = 1

        session_query_for_ids = MagicMock()
        session_query_for_ids.filter.return_value.all.return_value = [
            MagicMock(id="sess-1"),
            MagicMock(id="sess-2"),
        ]

        agent_run_query = MagicMock()
        agent_run_query.filter.return_value.delete.return_value = 2

        session_delete_query = MagicMock()
        session_delete_query.filter.return_value.delete.return_value = 2

        feedback_query = MagicMock()
        feedback_query.filter.return_value.delete.return_value = 0

        review_query = MagicMock()
        review_query.filter.return_value.delete.return_value = 0

        audit_query = MagicMock()
        audit_query.filter.return_value.update.return_value = 0

        def _query(model: Any) -> Any:
            from app.db.models import (  # noqa: I001
                AgentRun,
                AuditLog,
                Document,
                HumanReviewQueue,
                QueryFeedback,
                Session as DbSession,
            )
            mapping = {
                Document: document_query,
                DbSession: (
                    session_query_for_ids
                    if not hasattr(_query, "_session_seen")
                    else session_delete_query
                ),
                AgentRun: agent_run_query,
                QueryFeedback: feedback_query,
                HumanReviewQueue: review_query,
                AuditLog: audit_query,
            }
            if model.__name__ == "Session":
                if not hasattr(_query, "_session_seen"):
                    _query._session_seen = True  # type: ignore[attr-defined]
            return mapping[model]

        db.query.side_effect = _query

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/users/user-77")

        assert resp.status_code == 204
        agent_run_query.filter.return_value.delete.assert_called_once()
        from app.main import app
        app.dependency_overrides.clear()

    def test_deactivate_user_404_for_unknown(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if pk == "admin-1" else None

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/users/nonexistent-user")

        assert resp.status_code == 404
        from app.main import app
        app.dependency_overrides.clear()

    def test_cannot_deactivate_admin_user(self) -> None:
        admin = _make_admin_user()
        other_admin = _make_admin_user("admin-2")
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if pk == "admin-1" else other_admin

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/users/admin-2")

        assert resp.status_code == 400
        assert "admin users" in resp.json()["detail"]
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------


class TestReviewQueue:
    def _make_review_item(self) -> Any:
        item = MagicMock()
        item.id = "rq-1"
        item.session_id = "sess-1"
        item.user_id = "user-1"
        item.query = "Is this covered?"
        item.draft_answer = "Yes"
        item.citations_json = []
        item.risk_reason = "auto-flag"
        item.status = ReviewStatus.pending
        item.reviewed_by = None
        item.reviewed_at = None
        return item

    def test_list_review_queue_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        item = self._make_review_item()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [item]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/review-queue")

        assert resp.status_code == 200
        assert len(resp.json()) == 1
        from app.main import app
        app.dependency_overrides.clear()

    def test_approve_item_returns_approved(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        item = self._make_review_item()
        db.get.side_effect = lambda model, pk: admin if model is User else item

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post("/admin/review-queue/rq-1/approve")

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        from app.main import app
        app.dependency_overrides.clear()

    def test_reject_item_returns_rejected(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        item = self._make_review_item()
        db.get.side_effect = lambda model, pk: admin if model is User else item

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post("/admin/review-queue/rq-1/reject")

        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        from app.main import app
        app.dependency_overrides.clear()

    def test_approve_already_reviewed_returns_409(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        item = self._make_review_item()
        item.status = ReviewStatus.approved  # already done
        db.get.side_effect = lambda model, pk: admin if model is User else item

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post("/admin/review-queue/rq-1/approve")

        assert resp.status_code == 409
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Ingestion restart recovery
# ---------------------------------------------------------------------------


class TestIngestionRecovery:
    def test_recover_stuck_jobs_resets_status(self) -> None:
        from app.services.ingestion_service import recover_stuck_jobs

        stuck_job = MagicMock()
        stuck_job.id = "job-1"
        stuck_job.document_id = "doc-1"
        stuck_job.status = "embedding"

        doc = _make_document()
        doc.ingestion_started_at = datetime.now(UTC) - timedelta(minutes=30)
        db = MagicMock()
        (
            db.query.return_value.join.return_value.filter.return_value.all
        ).side_effect = [[stuck_job], []]
        db.get.return_value = doc

        count = recover_stuck_jobs(db)

        assert count == 1
        db.commit.assert_called_once()

    def test_recover_stuck_pending_jobs_marks_failed(self) -> None:
        from app.db.models import IngestionStatus
        from app.services.ingestion_service import recover_stuck_jobs

        pending_job = MagicMock()
        pending_job.id = "job-2"
        pending_job.document_id = "doc-2"
        pending_job.status = "pending"
        pending_job.created_at = datetime.now(UTC) - timedelta(minutes=30)

        doc = _make_document("doc-2")
        doc.ingestion_status = IngestionStatus.queued

        db = MagicMock()
        join_filter = db.query.return_value.join.return_value.filter.return_value
        join_filter.all.side_effect = [[], [pending_job]]
        db.get.return_value = doc

        count = recover_stuck_jobs(db)

        assert count == 1
        assert pending_job.status == "failed"
        assert doc.ingestion_status == IngestionStatus.failed
        db.commit.assert_called_once()

    def test_recover_stuck_pending_replacement_keeps_old_document_indexed(self) -> None:
        from app.db.models import DocumentVersion, DocumentVersionStatus, IngestionStatus
        from app.services.ingestion_service import recover_stuck_jobs

        pending_job = MagicMock()
        pending_job.id = "job-3"
        pending_job.document_id = "doc-3"
        pending_job.document_version_id = "version-2"
        pending_job.status = "pending"
        pending_job.created_at = datetime.now(UTC) - timedelta(minutes=30)

        doc = _make_document("doc-3")
        doc.ingestion_status = IngestionStatus.queued
        doc.version = 1
        doc.active_version = 1
        doc.active_version_id = "version-1"
        version = MagicMock()
        version.id = "version-2"
        version.status = DocumentVersionStatus.pending

        db = MagicMock()
        join_filter = db.query.return_value.join.return_value.filter.return_value
        join_filter.all.side_effect = [[], [pending_job]]
        db.get.side_effect = lambda model, pk: version if model is DocumentVersion else doc

        count = recover_stuck_jobs(db)

        assert count == 1
        assert pending_job.status == "failed"
        assert doc.version == 1
        assert doc.active_version == 1
        assert doc.ingestion_status == IngestionStatus.indexed
        assert version.status == DocumentVersionStatus.failed
        assert version.failed_reason is not None
        db.commit.assert_called_once()

    def test_recover_no_stuck_jobs_returns_zero(self) -> None:
        from app.services.ingestion_service import recover_stuck_jobs

        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = []

        count = recover_stuck_jobs(db)

        assert count == 0
        db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# run_ingestion background task
# ---------------------------------------------------------------------------


class TestRunIngestion:
    @pytest.mark.asyncio
    async def test_run_ingestion_marks_completed_on_success(self) -> None:
        from app.db.models import IngestionJob
        from app.services.ingestion_service import run_ingestion

        job = MagicMock()
        doc = MagicMock()
        mock_db = MagicMock()
        mock_db.get.side_effect = lambda model, pk: job if model is IngestionJob else doc

        mock_pipeline = MagicMock()
        mock_pipeline.ingest = AsyncMock()

        with patch("app.services.ingestion_service.SessionLocal", return_value=mock_db), \
             patch("app.services.ingestion_service.HybridRetriever"), \
             patch("app.services.ingestion_service.Reranker"), \
             patch("app.services.ingestion_service.RagPipeline", return_value=mock_pipeline):
            await run_ingestion("doc-1", "job-1", "/nonexistent/test.pdf", "test.pdf", "user-1")

        assert job.status == "completed"
        assert doc.ingestion_status == IngestionStatus.indexed
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_ingestion_marks_failed_on_error(self) -> None:
        from app.db.models import IngestionJob
        from app.services.ingestion_service import run_ingestion

        job = MagicMock()
        doc = MagicMock()
        mock_db = MagicMock()
        mock_db.get.side_effect = lambda model, pk: job if model is IngestionJob else doc

        mock_pipeline = MagicMock()
        mock_pipeline.ingest = AsyncMock(side_effect=RuntimeError("ingest failed"))

        with patch("app.services.ingestion_service.SessionLocal", return_value=mock_db), \
             patch("app.services.ingestion_service.HybridRetriever"), \
             patch("app.services.ingestion_service.Reranker"), \
             patch("app.services.ingestion_service.RagPipeline", return_value=mock_pipeline):
            await run_ingestion("doc-1", "job-1", "/nonexistent/test.pdf", "test.pdf", "user-1")

        assert job.status == "failed"
        assert job.error == "ingest failed"
        assert doc.ingestion_status == IngestionStatus.failed
        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 3C: trace_id generation and session state max-size
# ---------------------------------------------------------------------------


class TestPhase3CRuntimeHardening:
    @pytest.mark.asyncio
    async def test_run_agent_query_generates_trace_id_when_missing(self) -> None:
        from app.services.agent_runner import run_agent_query

        state = PrivateAIState(
            session_id="sess-1",
            user_id="user-1",
            messages=[Message(role="user", content="hello")],
            trace_id="",  # empty — should be filled in
        )
        final_state = state.model_copy(update={"status": "completed", "current_step": "respond"})

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=final_state)
        mock_db = MagicMock()
        mock_conv_mgr = MagicMock()
        mock_conv_mgr.save_session = MagicMock()

        await run_agent_query(state, mock_graph, db=mock_db, conversation_manager=mock_conv_mgr)

        # Verify ainvoke was called with a state that has trace_id set
        invoked_state = mock_graph.ainvoke.call_args[0][0]
        assert invoked_state.trace_id != "", "trace_id must be generated before graph.ainvoke"
        # Validate it's a valid UUID
        uuid.UUID(invoked_state.trace_id)

    @pytest.mark.asyncio
    async def test_two_turns_same_session_get_distinct_trace_ids(self) -> None:
        from app.services.agent_runner import run_agent_query

        base_state = PrivateAIState(
            session_id="sess-shared",
            user_id="user-1",
            messages=[Message(role="user", content="q1")],
        )

        async def invoke(s: Any) -> Any:
            return s.model_copy(update={"status": "completed", "current_step": "respond"})

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=invoke)
        mock_db = MagicMock()
        mock_conv_mgr = MagicMock()
        mock_conv_mgr.save_session = MagicMock()

        kw = {"db": mock_db, "conversation_manager": mock_conv_mgr}
        await run_agent_query(base_state, mock_graph, **kw)
        await run_agent_query(base_state, mock_graph, **kw)

        calls = mock_graph.ainvoke.call_args_list
        trace_id_1 = calls[0][0][0].trace_id
        trace_id_2 = calls[1][0][0].trace_id
        assert trace_id_1 != trace_id_2, "Each turn must produce a unique trace_id"
        assert calls[0][0][0].session_id == calls[1][0][0].session_id == "sess-shared"

    def test_save_session_raises_on_oversized_state(self) -> None:
        from app.services.conversation import ConversationManager

        db = MagicMock()
        mock_row = MagicMock()
        db.get.return_value = mock_row

        conv_mgr = ConversationManager(db)

        # Build a state with >1 MB of data
        big_content = "x" * 600_000
        state = PrivateAIState(
            session_id="sess-big",
            user_id="user-1",
            messages=[Message(role="user", content=big_content),
                      Message(role="assistant", content=big_content)],
        )

        with pytest.raises(ValueError, match="limit"):
            conv_mgr.save_session(state)


class TestMe:
    def test_get_me_returns_current_user(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/me")

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "admin@test.com"
        from app.main import app
        app.dependency_overrides.clear()


class TestTierEnforcement:
    def test_create_user_blocked_at_seat_cap(self) -> None:
        """POST /admin/users returns 422 when SeatLimitExceeded is raised."""
        from app.services.quota_service import SeatLimitExceeded

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.filter.return_value.first.return_value = None

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.user_routes.load_app_config",
            return_value={"tier": "evaluation", "max_seats": 2},
        ), patch(
            "app.api.user_routes.check_seat_limit",
            side_effect=SeatLimitExceeded("Seat limit reached (2/2 seats on evaluation tier)"),
        ):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={
                    "email": "x@test.com",
                    "password": "Strongpassword123!",
                    "role": "pilot_user",
                },
            )

        assert resp.status_code == 422
        assert "Seat limit" in resp.json()["detail"]
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_succeeds_below_seat_cap(self) -> None:
        """POST /admin/users succeeds when seat limit is not reached."""
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.filter.return_value.first.return_value = None

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.user_routes.load_app_config",
            return_value={"tier": "evaluation", "max_seats": 5},
        ), patch(
            "app.api.user_routes.check_seat_limit"
        ), patch(
            "app.api.user_routes.check_tier_expiry"
        ):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={
                    "email": "y@test.com",
                    "password": "Strongpassword123!",
                    "role": "pilot_user",
                },
            )

        assert resp.status_code == 201
        from app.main import app
        app.dependency_overrides.clear()

    def test_create_user_blocked_when_tier_expired(self) -> None:
        """POST /admin/users returns 403 when check_tier_expiry raises TierExpired."""
        from app.services.quota_service import TierExpired

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.user_routes.load_app_config", return_value={}
        ), patch(
            "app.api.user_routes.check_tier_expiry",
            side_effect=TierExpired("Evaluation period has expired. Contact us to upgrade."),
        ):
            client = _make_test_client(db, admin)
            resp = client.post(
                "/admin/users",
                json={
                    "email": "z@test.com",
                    "password": "Strongpassword123!",
                    "role": "pilot_user",
                },
            )

        assert resp.status_code == 403
        assert "expired" in resp.json()["detail"].lower()
        from app.main import app
        app.dependency_overrides.clear()

    def test_chat_blocked_when_quota_exceeded(self) -> None:
        """POST /chat returns 429 when QuotaExceeded is raised before LLM invocation."""
        from app.services.quota_service import QuotaExceeded

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.chat_routes.load_app_config", return_value={"monthly_query_limit": 5000}
        ), patch(
            "app.api.chat_routes.check_tier_expiry"
        ), patch(
            "app.api.chat_routes.check_cost_ceiling"
        ), patch(
            "app.api.chat_routes.check_query_quota",
            side_effect=QuotaExceeded(
                "Monthly query limit reached (5000/5000 queries on evaluation tier)"
            ),
        ):
            # LLM graph must NOT be called when quota is exceeded
            mock_graph = AsyncMock()
            client = _make_test_client(db, admin)
            client.app.state.graph = mock_graph
            resp = client.post(
                "/chat",
                json={"question": "What is the policy?"},
            )

        assert resp.status_code == 429
        assert "Monthly query limit" in resp.json()["detail"]
        mock_graph.ainvoke.assert_not_called()
        from app.main import app
        app.dependency_overrides.clear()

    def test_chat_stream_blocked_when_quota_exceeded(self) -> None:
        """POST /chat/stream returns 429 when QuotaExceeded fires before graph is invoked."""
        from app.services.quota_service import QuotaExceeded

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.chat_routes.load_app_config", return_value={"monthly_query_limit": 5000}
        ), patch(
            "app.api.chat_routes.check_tier_expiry"
        ), patch(
            "app.api.chat_routes.check_cost_ceiling"
        ), patch(
            "app.api.chat_routes.check_query_quota",
            side_effect=QuotaExceeded("Monthly query limit reached"),
        ):
            mock_graph = AsyncMock()
            client = _make_test_client(db, admin)
            client.app.state.graph = mock_graph
            resp = client.post(
                "/chat/stream",
                json={"question": "What is the policy?"},
            )

        assert resp.status_code == 429
        mock_graph.astream.assert_not_called()
        from app.main import app
        app.dependency_overrides.clear()
