"""Unit tests for workspace membership/authority logic (`workspace_service`).

Uses an in-memory SQLite DB with only the User/Workspace/WorkspaceMembership
tables (the rest of the schema needs pgvector, which SQLite lacks).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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


def _user(db: Session, uid: str, role: UserRole = UserRole.pilot_user) -> User:
    user = User(
        id=uid,
        email=f"{uid}@x.local",
        password_hash="x",  # noqa: S106 - test stub, not a real credential
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _seed_two_workspaces(db: Session) -> tuple[str, str]:
    a = ws.create_workspace(db, name="Legal", created_by="sys")
    b = ws.create_workspace(db, name="Finance", created_by="sys")
    return a.id, b.id


def test_member_sees_only_their_active_workspaces(db: Session) -> None:
    a_id, b_id = _seed_two_workspaces(db)
    user = _user(db, "u1")
    ws.add_member(db, workspace_id=a_id, user_id="u1")

    assert ws.list_workspace_ids_for_user(db, user) == [a_id]
    assert ws.is_member(db, user, a_id) is True
    assert ws.is_member(db, user, b_id) is False


def test_org_admin_spans_all_active_workspaces(db: Session) -> None:
    a_id, b_id = _seed_two_workspaces(db)
    admin = _user(db, "admin", role=UserRole.admin)

    assert set(ws.list_workspace_ids_for_user(db, admin)) == {a_id, b_id}
    assert ws.is_member(db, admin, a_id) is True
    assert ws.is_workspace_admin(db, admin, b_id) is True  # org-admin everywhere


def test_inactive_workspace_excluded(db: Session) -> None:
    a_id, b_id = _seed_two_workspaces(db)
    db.query(Workspace).filter(Workspace.id == b_id).update({"is_active": False})
    db.commit()
    admin = _user(db, "admin", role=UserRole.admin)

    assert ws.list_workspace_ids_for_user(db, admin) == [a_id]


def test_workspace_admin_vs_member_authority(db: Session) -> None:
    a_id, _ = _seed_two_workspaces(db)
    wadmin = _user(db, "wa")
    member = _user(db, "m")
    ws.add_member(db, workspace_id=a_id, user_id="wa", role=WorkspaceRole.workspace_admin)
    ws.add_member(db, workspace_id=a_id, user_id="m", role=WorkspaceRole.member)

    assert ws.is_workspace_admin(db, wadmin, a_id) is True
    assert ws.is_workspace_admin(db, member, a_id) is False


def test_assert_member_raises_for_non_member(db: Session) -> None:
    a_id, b_id = _seed_two_workspaces(db)
    user = _user(db, "u1")
    ws.add_member(db, workspace_id=a_id, user_id="u1")

    ws.assert_member(db, user, a_id)  # no raise
    with pytest.raises(ws.WorkspaceAccessDenied):
        ws.assert_member(db, user, b_id)


def test_sync_memberships_adds_updates_and_removes(db: Session) -> None:
    a_id, b_id = _seed_two_workspaces(db)
    c_id = ws.create_workspace(db, name="HR", created_by="sys").id
    _user(db, "u1")
    # Start in A (member) and B (member).
    ws.add_member(db, workspace_id=a_id, user_id="u1")
    ws.add_member(db, workspace_id=b_id, user_id="u1")

    # IdP now says: A (admin) + C (member); B should be removed.
    ws.sync_memberships(
        db,
        user_id="u1",
        workspace_ids=[a_id, c_id],
        admin_workspace_ids=[a_id],
    )

    roles = {
        m.workspace_id: m.role
        for m in db.query(WorkspaceMembership).filter(WorkspaceMembership.user_id == "u1")
    }
    assert roles == {a_id: WorkspaceRole.workspace_admin, c_id: WorkspaceRole.member}
    assert b_id not in roles
