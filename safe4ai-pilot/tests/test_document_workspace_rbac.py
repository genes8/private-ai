"""Document endpoint workspace RBAC (A6.1).

A workspace-admin of workspace A must not reach a document in workspace B: the
per-document endpoints return 404 for foreign documents (no IDOR disclosure).
Exercised against the real authorization helper with a SQLite-backed DB.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.middleware import encode_token
from app.db import Base, get_db
from app.db.models import (
    Document,
    IngestionJob,
    IngestionStatus,
    User,
    UserRole,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)
from app.main import app
from app.services import workspace_service as ws


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Workspace.__table__,
            WorkspaceMembership.__table__,
            Document.__table__,
            IngestionJob.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clear() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def _client(db: Session, uid: str, role: str) -> TestClient:
    def _override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)
    client.cookies.set("access_token", encode_token(uid, role))
    return client


def test_workspace_admin_cannot_inspect_foreign_doc(db: Session) -> None:
    # User administers workspace A; the document lives in workspace B.
    db.add(
        User(
            id="wa",
            email="wa@x.local",
            password_hash="x",  # noqa: S106 - test stub
            role=UserRole.pilot_user,
            is_active=True,
        )
    )
    a = ws.create_workspace(db, name="A", created_by="wa")
    b = ws.create_workspace(db, name="B", created_by="wa")
    ws.add_member(db, workspace_id=a.id, user_id="wa", role=WorkspaceRole.workspace_admin)
    db.add(
        Document(
            id="doc-b",
            filename="b.pdf",
            storage_filename="b.pdf",
            file_type="pdf",
            ingestion_status=IngestionStatus.indexed,
            uploaded_by="wa",
            workspace_id=b.id,
        )
    )
    db.commit()

    client = _client(db, "wa", "pilot_user")
    # Foreign document (workspace B) is indistinguishable from missing -> 404.
    assert client.get("/admin/documents/doc-b/status").status_code == 404
    assert client.get("/admin/documents/doc-b/inspect").status_code == 404


def test_org_admin_can_inspect_any_doc(db: Session) -> None:
    db.add(
        User(
            id="admin",
            email="admin@x.local",
            password_hash="x",  # noqa: S106 - test stub
            role=UserRole.admin,
            is_active=True,
        )
    )
    b = ws.create_workspace(db, name="B", created_by="admin")
    db.add(
        Document(
            id="doc-b",
            filename="b.pdf",
            storage_filename="b.pdf",
            file_type="pdf",
            ingestion_status=IngestionStatus.indexed,
            uploaded_by="admin",
            workspace_id=b.id,
        )
    )
    db.commit()

    client = _client(db, "admin", "admin")
    assert client.get("/admin/documents/doc-b/status").status_code == 200
