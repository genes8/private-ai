"""Endpoint tests for workspace management + RBAC (A6.3/A6.4/A6.5)."""

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
    AuditLog,
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
    # StaticPool + one shared connection so the TestClient's threadpool thread
    # sees the same in-memory schema/data the test set up.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Workspace.__table__,
            WorkspaceMembership.__table__,
            AuditLog.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _add_user(db: Session, uid: str, role: UserRole) -> None:
    db.add(
        User(
            id=uid,
            email=f"{uid}@x.local",
            password_hash="x",  # noqa: S106 - test stub
            role=role,
            is_active=True,
        )
    )
    db.commit()


def _client(db: Session, uid: str, role: str) -> TestClient:
    def _override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)
    client.cookies.set("access_token", encode_token(uid, role))
    client.cookies.set("csrf_token", "csrf")
    client.headers["X-CSRF-Token"] = "csrf"
    return client


@pytest.fixture(autouse=True)
def _clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def test_list_my_workspaces_returns_role(db: Session) -> None:
    _add_user(db, "wadmin", UserRole.pilot_user)
    w = ws.create_workspace(db, name="Legal", created_by="wadmin")
    ws.add_member(db, workspace_id=w.id, user_id="wadmin", role=WorkspaceRole.workspace_admin)

    client = _client(db, "wadmin", "pilot_user")
    resp = client.get("/workspaces")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Legal"
    assert body[0]["role"] == "workspace_admin"


def test_create_workspace_requires_org_admin(db: Session) -> None:
    _add_user(db, "member", UserRole.pilot_user)
    client = _client(db, "member", "pilot_user")
    resp = client.post("/admin/workspaces", json={"name": "Finance"})
    assert resp.status_code == 403


def test_org_admin_creates_workspace_and_audit(db: Session) -> None:
    _add_user(db, "admin", UserRole.admin)
    client = _client(db, "admin", "admin")

    resp = client.post("/admin/workspaces", json={"name": "Finance"})
    assert resp.status_code == 201
    assert resp.json()["role"] == "workspace_admin"

    # Creator is a workspace_admin and an audit event was recorded.
    ws_row = db.query(Workspace).filter(Workspace.name == "Finance").one()
    assert ws.is_workspace_admin(
        db, db.get(User, "admin"), ws_row.id
    )
    audit = db.query(AuditLog).filter(AuditLog.action_type == "workspace_created").all()
    assert len(audit) == 1
    assert audit[0].workspace_id == ws_row.id


def test_workspace_admin_adds_member(db: Session) -> None:
    _add_user(db, "wadmin", UserRole.pilot_user)
    _add_user(db, "newbie", UserRole.pilot_user)
    w = ws.create_workspace(db, name="Legal", created_by="wadmin")
    ws.add_member(db, workspace_id=w.id, user_id="wadmin", role=WorkspaceRole.workspace_admin)

    client = _client(db, "wadmin", "pilot_user")
    resp = client.post(
        f"/admin/workspaces/{w.id}/members", json={"user_id": "newbie", "role": "member"}
    )
    assert resp.status_code == 201
    assert ws.is_member(db, db.get(User, "newbie"), w.id)
    assert (
        db.query(AuditLog)
        .filter(AuditLog.action_type == "workspace_membership_granted")
        .count()
        == 1
    )


def test_non_admin_of_workspace_gets_404(db: Session) -> None:
    _add_user(db, "outsider", UserRole.pilot_user)
    _add_user(db, "owner", UserRole.pilot_user)
    w = ws.create_workspace(db, name="Legal", created_by="owner")
    ws.add_member(db, workspace_id=w.id, user_id="owner", role=WorkspaceRole.workspace_admin)

    client = _client(db, "outsider", "pilot_user")
    resp = client.post(
        f"/admin/workspaces/{w.id}/members", json={"user_id": "outsider", "role": "member"}
    )
    assert resp.status_code == 404
