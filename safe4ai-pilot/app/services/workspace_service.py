"""Workspace membership and authority helpers.

Pure functions over a SQLAlchemy ``Session`` (no FastAPI dependencies), mirroring
``quota_service``. The global ``UserRole.admin`` (org-admin) is treated as a
member-and-admin of every workspace; everyone else derives authority from
``WorkspaceMembership`` rows. Workspace authority is always resolved from the DB
per request — never trusted from the JWT — so membership changes take effect
immediately.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.db.models import (
    User,
    UserRole,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)


class WorkspaceAccessDenied(Exception):
    """Raised when a user is not a member of the requested workspace."""


def is_org_admin(user: User) -> bool:
    """True for the global admin role, which spans all workspaces."""
    return str(getattr(user.role, "value", user.role)) == UserRole.admin.value


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "workspace"


# --- reads -----------------------------------------------------------------


def list_active_workspace_ids(db: Session) -> list[str]:
    rows = db.query(Workspace.id).filter(Workspace.is_active.is_(True)).all()
    return [r[0] for r in rows]


def list_workspace_ids_for_user(db: Session, user: User) -> list[str]:
    """Workspaces the user may read from.

    Org-admins see every active workspace; members see the active workspaces they
    belong to.
    """
    if is_org_admin(user):
        return list_active_workspace_ids(db)
    rows = (
        db.query(WorkspaceMembership.workspace_id)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .filter(
            WorkspaceMembership.user_id == user.id,
            Workspace.is_active.is_(True),
        )
        .all()
    )
    return [r[0] for r in rows]


def user_workspace_role(db: Session, user_id: str, workspace_id: str) -> WorkspaceRole | None:
    membership = (
        db.query(WorkspaceMembership)
        .filter(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
        .one_or_none()
    )
    return membership.role if membership is not None else None


def is_member(db: Session, user: User, workspace_id: str) -> bool:
    if is_org_admin(user):
        return True
    return user_workspace_role(db, user.id, workspace_id) is not None


def is_workspace_admin(db: Session, user: User, workspace_id: str) -> bool:
    if is_org_admin(user):
        return True
    return user_workspace_role(db, user.id, workspace_id) == WorkspaceRole.workspace_admin


def assert_member(db: Session, user: User, workspace_id: str) -> None:
    """Raise WorkspaceAccessDenied unless the user may access the workspace."""
    if not is_member(db, user, workspace_id):
        raise WorkspaceAccessDenied(workspace_id)


# --- writes ----------------------------------------------------------------


def create_workspace(
    db: Session, *, name: str, created_by: str, slug: str | None = None, commit: bool = True
) -> Workspace:
    workspace = Workspace(
        id=str(uuid.uuid4()),
        name=name,
        slug=slug or _slugify(name),
        is_active=True,
        created_by=created_by,
    )
    db.add(workspace)
    if commit:
        db.commit()
    return workspace


def add_member(
    db: Session,
    *,
    workspace_id: str,
    user_id: str,
    role: WorkspaceRole = WorkspaceRole.member,
    commit: bool = True,
) -> WorkspaceMembership:
    """Add or update a membership (idempotent on the unique (workspace, user))."""
    membership = (
        db.query(WorkspaceMembership)
        .filter(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        .one_or_none()
    )
    if membership is None:
        membership = WorkspaceMembership(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        db.add(membership)
    else:
        membership.role = role
    if commit:
        db.commit()
    return membership


def set_member_role(
    db: Session, *, workspace_id: str, user_id: str, role: WorkspaceRole, commit: bool = True
) -> None:
    db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
    ).update({"role": role})
    if commit:
        db.commit()


def remove_member(db: Session, *, workspace_id: str, user_id: str, commit: bool = True) -> None:
    db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
    ).delete()
    if commit:
        db.commit()


def sync_memberships(
    db: Session,
    *,
    user_id: str,
    workspace_ids: list[str],
    admin_workspace_ids: list[str] | None = None,
    commit: bool = True,
) -> None:
    """Make the user's memberships match ``workspace_ids`` exactly (IdP-authoritative).

    Adds missing memberships, updates roles, and removes memberships no longer in
    the desired set. ``admin_workspace_ids`` (subset of ``workspace_ids``) grant
    the ``workspace_admin`` role.
    """
    admin_set = set(admin_workspace_ids or [])
    desired = set(workspace_ids)
    current = {
        m.workspace_id: m
        for m in db.query(WorkspaceMembership).filter(
            WorkspaceMembership.user_id == user_id
        )
    }
    for ws_id in desired:
        role = WorkspaceRole.workspace_admin if ws_id in admin_set else WorkspaceRole.member
        add_member(db, workspace_id=ws_id, user_id=user_id, role=role, commit=False)
    for ws_id in set(current) - desired:
        remove_member(db, workspace_id=ws_id, user_id=user_id, commit=False)
    if commit:
        db.commit()
