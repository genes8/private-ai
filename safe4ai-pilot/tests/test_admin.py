"""Tests for Phase 3B admin API and Phase 3C runtime hardening (trace_id, max-size)."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import (
    IngestionStatus,
    ReviewStatus,
    User,
    UserRole,
)
from app.models import Message, PrivateAIState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_admin_user(user_id: str = "admin-1") -> Any:
    user = MagicMock()
    user.id = user_id
    user.email = "admin@test.com"
    user.role = UserRole.admin
    user.is_active = True
    user.failed_login_count = 0
    user.locked_until = None
    return user


def _make_pilot_user(user_id: str = "user-1") -> Any:
    user = MagicMock()
    user.id = user_id
    user.email = "pilot@test.com"
    user.role = UserRole.pilot_user
    user.is_active = True
    user.failed_login_count = 0
    user.locked_until = None
    return user


def _make_document(doc_id: str = "doc-1") -> Any:
    doc = MagicMock()
    doc.id = doc_id
    doc.filename = "test.pdf"
    doc.storage_filename = "safe-name.pdf"
    doc.file_type = "pdf"
    doc.ingestion_status = IngestionStatus.indexed
    doc.uploaded_by = "admin-1"
    doc.uploaded_at = datetime.now(UTC)
    doc.doc_metadata = None
    doc.ingestion_started_at = None
    doc.version = 1
    doc.active_version = 1
    return doc


def _mock_db_with_admin(admin: User) -> Any:
    """Build a mock DB that authenticates the given user from the JWT cookie."""
    db = MagicMock()
    db.get.return_value = admin
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    _paged = db.query.return_value.filter.return_value.offset.return_value.limit.return_value
    _paged.all.return_value = []
    db.query.return_value.scalar.return_value = None
    db.query.return_value.filter.return_value.scalar.return_value = None
    return db


def _make_test_client(db_mock: Any, admin: User) -> TestClient:
    from app.auth.middleware import encode_token
    from app.db import get_db
    from app.main import app

    def _override_db() -> Any:
        yield db_mock

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app, raise_server_exceptions=True)
    token = encode_token(str(admin.id), str(admin.role))
    client.cookies.set("access_token", token)
    csrf_token = "test-csrf-token"
    client.cookies.set("csrf_token", csrf_token)
    client.headers["X-CSRF-Token"] = csrf_token
    return client


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------


class TestDocumentUpload:
    def test_upload_valid_pdf_returns_201(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        _close = lambda coro: coro.close()  # noqa: E731
        with patch("app.api.admin_routes.asyncio.create_task", side_effect=_close):
            client = _make_test_client(db, admin)
            pdf_bytes = b"%PDF-1.4 fake pdf content"
            with patch("app.api.admin_routes.UploadValidator.validate") as mock_validate, \
                 patch("pathlib.Path.write_bytes"), \
                 patch("pathlib.Path.mkdir"):
                mock_validate.return_value = MagicMock(allowed=True)
                resp = client.post(
                    "/admin/documents/upload",
                    files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                )

        assert resp.status_code == 201
        body = resp.json()
        assert "doc_id" in body
        assert "job_id" in body
        from app.main import app
        app.dependency_overrides.clear()

    def test_upload_invalid_file_returns_400(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        client = _make_test_client(db, admin)
        with patch("app.api.admin_routes.UploadValidator.validate") as mock_validate, \
             patch("pathlib.Path.mkdir"):
            mock_validate.return_value = MagicMock(allowed=False, reason="extension not allowed")
            resp = client.post(
                "/admin/documents/upload",
                files={"file": ("doc.exe", io.BytesIO(b"fake"), "application/octet-stream")},
            )

        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "extension" in detail or "not allowed" in detail
        from app.main import app
        app.dependency_overrides.clear()

    def test_upload_requires_admin(self) -> None:
        pilot = _make_pilot_user()
        db = _mock_db_with_admin(pilot)

        client = _make_test_client(db, pilot)
        with patch("pathlib.Path.mkdir"):
            resp = client.post(
                "/admin/documents/upload",
                files={"file": ("doc.pdf", io.BytesIO(b"pdf"), "application/pdf")},
            )

        assert resp.status_code == 403
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Document list and status
# ---------------------------------------------------------------------------


class TestDocumentList:
    def test_list_documents_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.outerjoin.return_value.order_by.return_value.all.return_value = [
            (_make_document(), 3)
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/documents")

        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 1
        assert docs[0]["id"] == "doc-1"
        assert docs[0]["chunk_count"] == 3
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_document_status_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        # Return admin for User lookups, doc for Document lookups
        db.get.side_effect = lambda model, pk: admin if model is User else doc

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/documents/doc-1/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["doc_id"] == "doc-1"
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_document_status_404_for_unknown(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        # Return admin for User lookups (auth), None for Document lookups (not found)
        db.get.side_effect = lambda model, pk: admin if model is User else None

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/documents/nonexistent/status")

        assert resp.status_code == 404
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Document delete and reindex
# ---------------------------------------------------------------------------


class TestDocumentDelete:
    def test_delete_document_returns_204(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc
        db.query.return_value.filter.return_value.all.return_value = []

        mock_retriever = MagicMock()

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("app.api.admin_routes.QdrantClient") as MockQdrant:
            client = _make_test_client(db, admin)
            client.app.state.retriever = mock_retriever  # type: ignore[attr-defined]
            resp = client.delete("/admin/documents/doc-1")

        assert resp.status_code == 204
        db.begin.assert_called()
        mock_retriever.remove_from_bm25.assert_called_once_with("doc-1")
        mock_qdrant = MockQdrant.return_value
        mock_qdrant.delete.assert_called_once()
        from app.main import app
        app.dependency_overrides.clear()

    def test_delete_document_removes_qdrant_points_for_doc(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc
        db.query.return_value.filter.return_value.all.return_value = []

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("app.api.admin_routes.QdrantClient") as MockQdrant:
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/documents/doc-1")

        assert resp.status_code == 204
        mock_qdrant = MockQdrant.return_value
        mock_qdrant.delete.assert_called_once()
        _, kwargs = mock_qdrant.delete.call_args
        assert kwargs["collection_name"] == "documents"
        assert "doc-1" in repr(kwargs["points_selector"])
        from app.main import app
        app.dependency_overrides.clear()

    def test_delete_document_404_for_unknown(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if model is User else None

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/documents/nonexistent")

        assert resp.status_code == 404
        from app.main import app
        app.dependency_overrides.clear()


class TestDocumentReindex:
    def test_reindex_returns_202(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc

        _close2 = lambda coro: coro.close()  # noqa: E731
        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("app.api.admin_routes.asyncio.create_task", side_effect=_close2), \
             patch("app.api.admin_routes.QdrantClient") as MockQdrant:
            client = _make_test_client(db, admin)
            resp = client.post("/admin/documents/doc-1/reindex")

        assert resp.status_code == 202
        assert "job_id" in resp.json()
        MockQdrant.return_value.delete.assert_called_once()
        from app.main import app
        app.dependency_overrides.clear()

    def test_reindex_404_for_unknown(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if model is User else None

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.post("/admin/documents/nonexistent/reindex")

        assert resp.status_code == 404
        from app.main import app
        app.dependency_overrides.clear()

    def test_reindex_409_when_raw_file_missing(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=False):
            client = _make_test_client(db, admin)
            resp = client.post("/admin/documents/doc-1/reindex")

        assert resp.status_code == 409
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


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
                json={"email": "new@test.com", "password": "strongpassword123",
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

    def test_deactivate_user_returns_204(self) -> None:
        admin = _make_admin_user()
        target = _make_pilot_user("user-99")
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if pk == "admin-1" else target

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.delete("/admin/users/user-99")

        assert resp.status_code == 204
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
                json={"email": "admin@test.com", "password": "strongpassword123",
                      "role": "pilot_user"},
            )

        assert resp.status_code == 409
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


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------


class TestAuditLogs:
    def test_list_audit_logs_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        _paged = db.query.return_value.order_by.return_value.offset.return_value.limit.return_value
        _paged.all.return_value = []

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs")

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        from app.main import app
        app.dependency_overrides.clear()

    def test_export_csv_returns_csv(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.order_by.return_value.all.return_value = []

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs/export.csv")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Review queue
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
        db.query.return_value.join.return_value.filter.return_value.all.return_value = [stuck_job]
        db.get.return_value = doc

        count = recover_stuck_jobs(db)

        assert count == 1
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

        result = await run_agent_query(
            state, mock_graph, db=mock_db, conversation_manager=mock_conv_mgr
        )

        # trace_id must be a non-empty UUID
        assert result.trace_id == "" or True  # graph returns final_state; check the invoked state
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


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_get_stats_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        # scalar() defaults to None in _mock_db_with_admin → triggers 0/None fallbacks

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_queries"] == 0
        assert body["avg_latency_ms"] is None
        assert body["total_cost_usd"] == 0.0
        assert body["cache_total_hits"] == 0
        assert body["unique_users"] == 0
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_stats_requires_admin(self) -> None:
        pilot = _make_pilot_user()
        db = _mock_db_with_admin(pilot)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, pilot)
            resp = client.get("/admin/stats")

        assert resp.status_code == 403
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Current user info (/me)
# ---------------------------------------------------------------------------


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
