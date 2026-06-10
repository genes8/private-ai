"""Phase D: atomic document replacement, rollback window, deletion verification."""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import IngestionJob, IngestionStatus
from app.services.document_service import (
    activate_document_version,
    cleanup_superseded_chunk_rows,
    delete_superseded_points,
    verify_document_deletion,
)
from tests.test_admin import (
    _close_and_return_task,
    _make_admin_user,
    _make_document,
    _make_test_client,
    _mock_db_with_admin,
)

# ---------------------------------------------------------------------------
# activate_document_version — switch ordering
# ---------------------------------------------------------------------------


def test_activate_sets_new_version_active_before_superseding_old() -> None:
    with patch("app.services.document_service.QdrantClient") as mock_client_cls:
        client = mock_client_cls.return_value
        activate_document_version("doc-1", 3)

    calls = client.set_payload.call_args_list
    assert len(calls) == 2
    # First call activates the new version; second supersedes the rest.
    assert calls[0].kwargs["payload"] == {"is_active": True}
    assert calls[1].kwargs["payload"]["is_active"] is False
    assert "superseded_at" in calls[1].kwargs["payload"]


def test_delete_superseded_points_filters_on_age() -> None:
    with patch("app.services.document_service.QdrantClient") as mock_client_cls:
        client = mock_client_cls.return_value
        delete_superseded_points(older_than_hours=24.0)

    selector = client.delete.call_args.kwargs["points_selector"]
    keys = [c.key for c in selector.must]
    assert "is_active" in keys
    assert "superseded_at" in keys


def test_cleanup_superseded_chunk_rows_deletes_non_active_versions() -> None:
    db = MagicMock()
    db.query.return_value.all.return_value = [("doc-1", 2)]
    db.query.return_value.filter.return_value.delete.return_value = 5

    deleted = cleanup_superseded_chunk_rows(db)

    assert deleted == 5
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# run_ingestion with activate_version — atomic switch semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replacement_ingest_stages_then_activates() -> None:
    from app.services.ingestion_service import run_ingestion

    job = MagicMock()
    doc = MagicMock()
    doc.version = 2
    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: job if model is IngestionJob else doc

    mock_pipeline = MagicMock()
    mock_pipeline.ingest = AsyncMock()
    retriever = MagicMock()

    with patch("app.services.ingestion_service.SessionLocal", return_value=mock_db), patch(
        "app.services.ingestion_service.Reranker"
    ), patch("app.services.ingestion_service.RagPipeline", return_value=mock_pipeline), patch(
        "app.services.ingestion_service.activate_document_version"
    ) as mock_activate:
        await run_ingestion(
            "doc-1",
            "job-1",
            "/nonexistent/v2.pdf",
            "v2.pdf",
            "user-1",
            retriever=retriever,
            activate_version=2,
        )

    # Staged ingest: not active during embedding
    assert mock_pipeline.ingest.call_args.kwargs["activate"] is False
    mock_activate.assert_called_once_with("doc-1", 2)
    assert doc.active_version == 2
    retriever.rebuild_from_qdrant.assert_called_once()
    assert job.status == "completed"


@pytest.mark.asyncio
async def test_failed_replacement_keeps_previous_version_serving() -> None:
    from app.services.ingestion_service import run_ingestion

    job = MagicMock()
    doc = MagicMock()
    doc.version = 2
    doc.active_version = 1
    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: job if model is IngestionJob else doc

    mock_pipeline = MagicMock()
    mock_pipeline.ingest = AsyncMock(side_effect=RuntimeError("embedding service down"))

    with patch("app.services.ingestion_service.SessionLocal", return_value=mock_db), patch(
        "app.services.ingestion_service.HybridRetriever"
    ), patch("app.services.ingestion_service.Reranker"), patch(
        "app.services.ingestion_service.RagPipeline", return_value=mock_pipeline
    ), patch("app.services.ingestion_service.activate_document_version") as mock_activate:
        await run_ingestion(
            "doc-1", "job-1", "/nonexistent/v2.pdf", "v2.pdf", "user-1", activate_version=2
        )

    # The switch never happened: previous version remains active and the
    # document is still usable (indexed), only the job records the failure.
    mock_activate.assert_not_called()
    assert doc.active_version == 1
    assert doc.ingestion_status == IngestionStatus.indexed
    assert job.status == "failed"


# ---------------------------------------------------------------------------
# verify_document_deletion
# ---------------------------------------------------------------------------


def _db_with_counts(chunks: int, jobs: int, cache: int) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.side_effect = [chunks, jobs]
    db.execute.return_value.scalar.return_value = cache
    return db


def test_verify_deletion_clean_when_all_stores_empty() -> None:
    db = _db_with_counts(0, 0, 0)
    retriever = MagicMock()
    retriever._bm25_payloads = {"c1": {"doc_id": "other-doc"}}

    with patch("app.services.document_service.QdrantClient") as mock_client_cls:
        mock_client_cls.return_value.count.return_value.count = 0
        report = verify_document_deletion(db, retriever, "doc-1")

    assert report["clean"] is True
    assert report["counts"]["bm25_entries"] == 0


def test_verify_deletion_flags_lingering_vectors() -> None:
    db = _db_with_counts(0, 0, 0)

    with patch("app.services.document_service.QdrantClient") as mock_client_cls:
        mock_client_cls.return_value.count.return_value.count = 7
        report = verify_document_deletion(db, None, "doc-1")

    assert report["clean"] is False
    assert report["counts"]["qdrant_points"] == 7


# ---------------------------------------------------------------------------
# Routes: upload-new-version and verify-deletion
# ---------------------------------------------------------------------------


class TestUploadNewVersion:
    def test_upload_new_version_returns_202_and_bumps_version(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        doc.version = 1
        from app.db.models import User

        db.get.side_effect = lambda model, pk: admin if model is User else doc
        db.query.return_value.filter.return_value.first.return_value = None

        with patch(
            "app.api.document_routes.asyncio.create_task", side_effect=_close_and_return_task
        ):
            client = _make_test_client(db, admin)
            with patch("app.api.document_routes.UploadValidator.validate") as mock_validate, patch(
                "app.api.document_routes.UploadValidator.safe_filename",
                return_value="safe-v2",
            ), patch("pathlib.Path.write_bytes"), patch("pathlib.Path.mkdir"):
                mock_validate.return_value = MagicMock(allowed=True)
                resp = client.post(
                    "/admin/documents/doc-1/upload-new-version",
                    files={"file": ("v2.pdf", io.BytesIO(b"%PDF-1.4 v2"), "application/pdf")},
                )

        assert resp.status_code == 202
        body = resp.json()
        assert body["version"] == 2
        assert doc.version == 2
        # Serving version must NOT switch at upload time — only after ingest.
        assert doc.active_version != 2 or doc.active_version == 1
        from app.main import app

        app.dependency_overrides.clear()

    def test_upload_new_version_409_when_ingestion_active(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        from app.db.models import User

        db.get.side_effect = lambda model, pk: admin if model is User else doc
        db.query.return_value.filter.return_value.first.return_value = MagicMock()  # active job

        client = _make_test_client(db, admin)
        with patch("app.api.document_routes.UploadValidator.validate") as mock_validate, patch(
            "pathlib.Path.write_bytes"
        ), patch("pathlib.Path.mkdir"):
            mock_validate.return_value = MagicMock(allowed=True)
            resp = client.post(
                "/admin/documents/doc-1/upload-new-version",
                files={"file": ("v2.pdf", io.BytesIO(b"%PDF-1.4 v2"), "application/pdf")},
            )

        assert resp.status_code == 409
        from app.main import app

        app.dependency_overrides.clear()

    def test_upload_new_version_404_for_unknown_document(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        from app.db.models import User

        db.get.side_effect = lambda model, pk: admin if model is User else None

        client = _make_test_client(db, admin)
        with patch("pathlib.Path.mkdir"):
            resp = client.post(
                "/admin/documents/nope/upload-new-version",
                files={"file": ("v2.pdf", io.BytesIO(b"%PDF-1.4 v2"), "application/pdf")},
            )

        assert resp.status_code == 404
        from app.main import app

        app.dependency_overrides.clear()


class TestVerifyDeletion:
    def test_verify_deletion_409_while_document_exists(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        doc = _make_document()
        from app.db.models import User

        db.get.side_effect = lambda model, pk: admin if model is User else doc

        client = _make_test_client(db, admin)
        with patch("pathlib.Path.mkdir"):
            resp = client.get("/admin/documents/doc-1/verify-deletion")

        assert resp.status_code == 409
        from app.main import app

        app.dependency_overrides.clear()

    def test_verify_deletion_reports_after_delete(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        from app.db.models import User

        db.get.side_effect = lambda model, pk: admin if model is User else None

        client = _make_test_client(db, admin)
        with patch("pathlib.Path.mkdir"), patch(
            "app.api.document_routes.verify_document_deletion",
            return_value={"doc_id": "doc-1", "clean": True, "counts": {}},
        ) as mock_verify:
            resp = client.get("/admin/documents/doc-1/verify-deletion")

        assert resp.status_code == 200
        assert resp.json()["clean"] is True
        mock_verify.assert_called_once()
        from app.main import app

        app.dependency_overrides.clear()
