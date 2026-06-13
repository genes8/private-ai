import os
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text

from app.config import Settings
from tests.fixtures.scanned_pdf import write_scanned_pdf
from tests.helpers.smoke_client import SmokeClient

pytestmark = pytest.mark.smoke


def _require_real_smoke() -> None:
    if os.getenv("RUN_REAL_SMOKE") != "1":
        pytest.skip(
            "Set RUN_REAL_SMOKE=1 after `docker compose up` to run real-service smoke tests"
        )


def test_real_fastapi_health_endpoint() -> None:
    _require_real_smoke()

    response = httpx.get("http://localhost:8000/health", timeout=10)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_real_qdrant_ready_endpoint() -> None:
    _require_real_smoke()

    settings = Settings()
    response = httpx.get(f"{settings.qdrant_url}/readyz", timeout=10)

    assert response.status_code == 200


def test_real_ollama_tags_endpoint() -> None:
    _require_real_smoke()

    settings = Settings()
    response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=10)
    model_names = {model["name"] for model in response.json().get("models", [])}

    assert response.status_code == 200
    assert settings.ollama_model in model_names
    assert settings.embedding_model in model_names


def test_real_postgres_pgvector_extension() -> None:
    _require_real_smoke()

    settings = Settings()
    engine = create_engine(settings.postgres_url)

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        extension = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()

    assert extension == "vector"


# --- end-to-end document-flow smoke tests --------------------------------------
# These exercise the live ingestion/admin pipeline. They need admin credentials
# (SMOKE_ADMIN_PASSWORD or SEED_ADMIN_PASSWORD) in addition to RUN_REAL_SMOKE=1.


def test_real_scanned_pdf_ocr_ingest(tmp_path: Path) -> None:
    """An image-only PDF ingests via the OCR path and yields readable chunks."""
    _require_real_smoke()

    pdf = write_scanned_pdf(tmp_path / "scanned-sample.pdf")
    with SmokeClient() as client:
        doc_id = client.upload_document(pdf)
        try:
            status = client.wait_for_indexed(doc_id)
            assert status["ingestion_status"] == "indexed", status

            inspect = client.inspect(doc_id)
            # OCR must have produced chunks from an image-only PDF.
            assert inspect["chunk_count"] > 0, inspect
            previews = " ".join(
                (c.get("content_preview") or "") for c in inspect["chunks"]
            ).lower()
            assert previews.strip(), "OCR produced no readable text"
            # OCR is fuzzy; accept any of the distinctive fixture tokens.
            assert any(
                token in previews
                for token in ("safe4ai", "invoice", "northwind", "vendor")
            ), f"OCR text did not contain expected tokens: {previews[:200]!r}"
        finally:
            client.delete(f"/admin/documents/{doc_id}")


def test_real_upload_new_version_no_retrieval_gap(tmp_path: Path) -> None:
    """Staged new-version ingest keeps a servable version at every moment."""
    _require_real_smoke()

    pdf = write_scanned_pdf(tmp_path / "doc-v1.pdf")
    with SmokeClient() as client:
        doc_id = client.upload_document(pdf)
        try:
            first = client.wait_for_indexed(doc_id)
            assert first["ingestion_status"] == "indexed"
            original_version_id = first["active_version_id"]
            assert original_version_id is not None

            result = client.upload_new_version(doc_id, tmp_path / "doc-v1.pdf")
            assert result["version"] >= 2

            # Poll throughout the staged ingest: the document must never drop out
            # of a servable state, and a previous version must always be active
            # until the atomic flip completes.
            deadline = time.monotonic() + 180
            flipped = False
            while time.monotonic() < deadline:
                status = client.status(doc_id)
                assert status["ingestion_status"] != "failed", status
                assert status["active_version_id"] is not None, status
                if status["active_version_id"] != original_version_id:
                    flipped = True
                    break
                time.sleep(2)
            assert flipped, "new version never became active within timeout"
            # After the flip the document is still indexed and servable.
            assert client.status(doc_id)["ingestion_status"] == "indexed"
        finally:
            client.delete(f"/admin/documents/{doc_id}")


def test_real_delete_then_verify_deletion_clean(tmp_path: Path) -> None:
    """Deleting a document leaves no retrievable remnants in any store."""
    _require_real_smoke()

    pdf = write_scanned_pdf(tmp_path / "to-delete.pdf")
    with SmokeClient() as client:
        doc_id = client.upload_document(pdf)
        client.wait_for_indexed(doc_id)

        deleted = client.delete(f"/admin/documents/{doc_id}")
        assert deleted.status_code == 204, deleted.text

        verify = client.get(f"/admin/documents/{doc_id}/verify-deletion")
        assert verify.status_code == 200, verify.text
        body = verify.json()
        assert body["clean"] is True, body["counts"]
        assert all(count == 0 for count in body["counts"].values()), body["counts"]
