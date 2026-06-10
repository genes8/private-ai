from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db.models import DocumentVersionStatus, IngestionStatus, User, UserRole


def make_admin_user(user_id: str = "admin-1") -> Any:
    user = MagicMock()
    user.id = user_id
    user.email = "admin@test.com"
    user.role = UserRole.admin
    user.is_active = True
    user.failed_login_count = 0
    user.locked_until = None
    return user


def make_pilot_user(user_id: str = "user-1") -> Any:
    user = MagicMock()
    user.id = user_id
    user.email = "pilot@test.com"
    user.role = UserRole.pilot_user
    user.is_active = True
    user.failed_login_count = 0
    user.locked_until = None
    return user


def make_document(doc_id: str = "doc-1") -> Any:
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
    doc.file_size_bytes = 123
    doc.version = 1
    doc.active_version = 1
    doc.active_version_id = "version-1"
    doc.title = "test.pdf"
    doc.pending_version = None
    doc.pending_filename = None
    doc.pending_storage_filename = None
    doc.pending_file_type = None
    doc.pending_file_size_bytes = None
    return doc


def make_document_version(
    version_id: str = "version-1",
    *,
    doc_id: str = "doc-1",
    version_number: int = 1,
    status: DocumentVersionStatus = DocumentVersionStatus.active,
) -> Any:
    version = MagicMock()
    version.id = version_id
    version.document_id = doc_id
    version.version_number = version_number
    version.filename = "test.pdf" if version_number == 1 else f"v{version_number}.pdf"
    version.storage_filename = (
        "safe-name.pdf" if version_number == 1 else f"safe-v{version_number}.pdf"
    )
    version.file_type = "pdf"
    version.file_size_bytes = 123 if version_number == 1 else 456
    version.checksum = f"sha256-{version_number}"
    version.status = status
    version.created_by = "admin-1"
    version.created_at = datetime.now(UTC)
    version.ingestion_started_at = None
    version.ingested_at = None
    version.activated_at = version.created_at if status == DocumentVersionStatus.active else None
    version.failed_at = None
    version.failed_reason = None
    return version


def mock_db_with_admin(admin: User) -> Any:
    """Build a mock DB that authenticates the given user from the JWT cookie."""
    db = MagicMock()
    db.get.return_value = admin
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    paged = db.query.return_value.filter.return_value.offset.return_value.limit.return_value
    paged.all.return_value = []
    db.query.return_value.scalar.return_value = None
    db.query.return_value.filter.return_value.scalar.return_value = None
    return db


def make_test_client(db_mock: Any, admin: User) -> TestClient:
    from app.auth.middleware import encode_token
    from app.db import get_db
    from app.main import app

    def _override_db() -> Any:
        yield db_mock

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app, raise_server_exceptions=True)
    token = encode_token(str(admin.id), str(admin.role))
    client.cookies.set("access_token", token)
    csrf_token = "test-csrf-token"  # noqa: S105
    client.cookies.set("csrf_token", csrf_token)
    client.headers["X-CSRF-Token"] = csrf_token
    return client


def close_and_return_task(coro: Any) -> MagicMock:
    coro.close()
    task = MagicMock()
    task.cancelled.return_value = False
    task.exception.return_value = None
    return task
