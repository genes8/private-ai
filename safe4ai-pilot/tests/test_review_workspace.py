"""Review-queue workspace scoping (A6.6).

A workspace-admin sees and acts on only their workspaces' review items; a foreign
item is 404 (no IDOR). Org-admin is unrestricted.
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
    HumanReviewQueue,
    ReviewStatus,
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
            HumanReviewQueue.__table__,
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
    client.cookies.set("csrf_token", "csrf")
    client.headers["X-CSRF-Token"] = "csrf"
    return client


def _seed(db: Session) -> tuple[str, str]:
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
    for item_id, ws_id in (("item-a", a.id), ("item-b", b.id)):
        db.add(
            HumanReviewQueue(
                id=item_id,
                session_id="s",
                workspace_id=ws_id,
                user_id="wa",
                query="q",
                status=ReviewStatus.pending,
            )
        )
    db.commit()
    return a.id, b.id


def test_review_list_scoped_to_admin_workspaces(db: Session) -> None:
    _seed(db)
    client = _client(db, "wa", "pilot_user")
    resp = client.get("/admin/review-queue")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert ids == ["item-a"]  # workspace B's item is not visible


def test_approve_foreign_workspace_item_is_404(db: Session) -> None:
    _seed(db)
    client = _client(db, "wa", "pilot_user")
    assert client.post("/admin/review-queue/item-b/approve").status_code == 404
    # Own item approves fine.
    assert client.post("/admin/review-queue/item-a/approve").status_code == 200
