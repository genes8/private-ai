"""Admin document route tests."""

from __future__ import annotations

import io
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import DocumentVersionStatus, IngestionStatus, User
from tests.helpers.admin_routes import (
    close_and_return_task as _close_and_return_task,
)
from tests.helpers.admin_routes import (
    make_admin_user as _make_admin_user,
)
from tests.helpers.admin_routes import (
    make_document as _make_document,
)
from tests.helpers.admin_routes import (
    make_document_version as _make_document_version,
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


@pytest.fixture(autouse=True)
def _stub_workspace_resolution() -> Generator[None, None, None]:
    """Resolve the active/admin workspace for the mocked-DB document tests.

    Only workspace *resolution* is stubbed; is_workspace_admin keeps its real
    logic so org-admin (201) and non-admin (403) upload paths still differ.
    """
    from app.services import workspace_service

    with (
        patch.object(workspace_service, "assert_member", return_value=None),
        patch.object(
            workspace_service, "list_workspace_ids_for_user", return_value=["ws-test"]
        ),
        patch.object(
            workspace_service, "list_admin_workspace_ids_for_user", return_value=["ws-test"]
        ),
    ):
        yield


class TestDocumentUpload:
    def test_upload_valid_pdf_returns_201(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch(
            "app.api.document_routes.asyncio.create_task",
            side_effect=_close_and_return_task,
        ):
            client = _make_test_client(db, admin)
            pdf_bytes = b"%PDF-1.4 fake pdf content"
            with patch("app.api.document_routes.UploadValidator.validate") as mock_validate, \
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
        with patch("app.api.document_routes.UploadValidator.validate") as mock_validate, \
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
        (
            db.query.return_value.outerjoin.return_value.outerjoin.return_value
            .filter.return_value.order_by.return_value.all
        ).return_value = [(_make_document(), 3, "admin@test.com")]

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

    def test_inspect_document_returns_metadata_chunks_and_jobs(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc

        chunk = MagicMock()
        chunk.chunk_index = 0
        chunk.chunk_version = 1
        chunk.content_preview = "First chunk preview"
        chunk.qdrant_point_id = "point-1"

        job = MagicMock()
        job.status = "completed"
        job.created_at = datetime.now(UTC)
        job.completed_at = datetime.now(UTC)
        job.error = None

        _filtered = db.query.return_value.filter.return_value
        _filtered.scalar.return_value = 12
        _filtered.order_by.return_value.limit.return_value.all.side_effect = [[chunk], [job]]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/documents/doc-1/inspect")

        assert resp.status_code == 200
        body = resp.json()
        assert body["document"]["id"] == "doc-1"
        assert body["chunk_count"] == 12
        assert body["chunks"][0]["indexed"] is True
        assert body["chunks"][0]["content_preview"] == "First chunk preview"
        assert body["jobs"][0]["status"] == "completed"
        from app.main import app
        app.dependency_overrides.clear()

    def test_list_document_versions_returns_history(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        doc.active_version_id = "version-2"
        version_1 = _make_document_version(
            "version-1", version_number=1, status=DocumentVersionStatus.superseded
        )
        version_2 = _make_document_version(
            "version-2", version_number=2, status=DocumentVersionStatus.active
        )
        db.get.side_effect = lambda model, pk: admin if model is User else doc
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            version_2,
            version_1,
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/documents/doc-1/versions")

        assert resp.status_code == 200
        body = resp.json()
        assert [v["version_number"] for v in body["versions"]] == [2, 1]
        assert body["versions"][0]["id"] == "version-2"
        assert body["versions"][0]["status"] == "active"
        assert body["active_version_id"] == "version-2"
        from app.main import app
        app.dependency_overrides.clear()

    def test_inspect_document_404_for_unknown(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if model is User else None

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/documents/nonexistent/inspect")

        assert resp.status_code == 404
        from app.main import app
        app.dependency_overrides.clear()

    def test_inspect_document_rejects_bad_chunk_limit(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/documents/doc-1/inspect?chunk_limit=500")

        assert resp.status_code == 422
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
             patch("app.services.document_service.QdrantClient") as MockQdrant:
            client = _make_test_client(db, admin)
            client.app.state.retriever = mock_retriever  # type: ignore[attr-defined]
            resp = client.delete("/admin/documents/doc-1")

        assert resp.status_code == 204
        db.commit.assert_called()
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
             patch("app.services.document_service.QdrantClient") as MockQdrant:
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

    def test_delete_document_cancels_registered_ingestion_task(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc
        db.query.return_value.filter.return_value.first.return_value = None

        task = MagicMock()
        task.cancelled.return_value = False
        task.done.return_value = False

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("app.services.document_service.QdrantClient"):
            client = _make_test_client(db, admin)
            client.app.state.ingestion_tasks_by_doc = {"doc-1": task}  # type: ignore[attr-defined]
            resp = client.delete("/admin/documents/doc-1")

        assert resp.status_code == 204
        task.cancel.assert_called_once()
        from app.main import app
        app.dependency_overrides.clear()


class TestDocumentReindex:
    def test_reindex_returns_202(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch(
                 "app.api.document_routes.asyncio.create_task",
                 side_effect=_close_and_return_task,
             ), \
             patch("app.services.document_service.QdrantClient") as MockQdrant:
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

    def test_reindex_qdrant_failure_does_not_delete_db_chunks_or_schedule(self) -> None:
        """Qdrant delete failure must stop reindex to avoid stale vector hits."""
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        db.get.side_effect = lambda model, pk: admin if model is User else doc

        ingestion_job_query = MagicMock()
        ingestion_job_query.filter.return_value.first.return_value = None
        document_chunk_query = MagicMock()
        document_chunk_query.filter.return_value.delete.return_value = 1
        generic_query = MagicMock()

        def _query(model: Any) -> Any:
            from app.db.models import DocumentChunk, IngestionJob
            if model is IngestionJob:
                return ingestion_job_query
            if model is DocumentChunk:
                return document_chunk_query
            return generic_query

        db.query.side_effect = _query

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch(
                 "app.api.document_routes.delete_qdrant_points",
                 side_effect=RuntimeError("qdrant down"),
             ), \
             patch("app.api.document_routes._schedule_ingestion_task") as mock_schedule:
            client = _make_test_client(db, admin)
            resp = client.post("/admin/documents/doc-1/reindex")

        assert resp.status_code == 502
        document_chunk_query.filter.return_value.delete.assert_not_called()
        mock_schedule.assert_not_called()
        assert doc.ingestion_status == IngestionStatus.failed
        from app.main import app
        app.dependency_overrides.clear()

    def test_reindex_active_job_does_not_mutate_indexes(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        active_job = MagicMock()
        db.get.side_effect = lambda model, pk: admin if model is User else doc
        db.query.return_value.filter.return_value.first.return_value = active_job

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("app.api.document_routes.delete_qdrant_points") as mock_delete_qdrant:
            client = _make_test_client(db, admin)
            resp = client.post("/admin/documents/doc-1/reindex")

        assert resp.status_code == 409
        mock_delete_qdrant.assert_not_called()
        from app.main import app
        app.dependency_overrides.clear()
