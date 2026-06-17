"""Audit/stats view workspace scoping (A6.2).

Pins the authorization scope: org-admin is unrestricted (None), a workspace-admin
is scoped to the workspaces they administer, and a plain member is forbidden.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.audit_routes import _resolve_audit_scope
from app.db import Base
from app.db.models import User, UserRole, Workspace, WorkspaceMembership, WorkspaceRole
from app.services import workspace_service as ws


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, Workspace.__table__, WorkspaceMembership.__table__],
    )
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _user(db: Session, uid: str, role: UserRole) -> User:
    u = User(
        id=uid,
        email=f"{uid}@x.local",
        password_hash="x",  # noqa: S106 - test stub
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


def test_org_admin_is_unrestricted(db: Session) -> None:
    admin = _user(db, "admin", UserRole.admin)
    assert _resolve_audit_scope(db, admin) is None


def test_workspace_admin_scoped_to_their_workspaces(db: Session) -> None:
    user = _user(db, "wa", UserRole.pilot_user)
    a = ws.create_workspace(db, name="A", created_by="wa")
    b = ws.create_workspace(db, name="B", created_by="sys")
    ws.add_member(db, workspace_id=a.id, user_id="wa", role=WorkspaceRole.workspace_admin)
    ws.add_member(db, workspace_id=b.id, user_id="wa", role=WorkspaceRole.member)

    scope = _resolve_audit_scope(db, user)
    assert scope == [a.id]  # only the workspace they administer, not B


def test_plain_member_is_forbidden(db: Session) -> None:
    user = _user(db, "m", UserRole.pilot_user)
    a = ws.create_workspace(db, name="A", created_by="sys")
    ws.add_member(db, workspace_id=a.id, user_id="m", role=WorkspaceRole.member)

    with pytest.raises(HTTPException) as exc:
        _resolve_audit_scope(db, user)
    assert exc.value.status_code == 403
