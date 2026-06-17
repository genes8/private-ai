"""Workspace + membership management endpoints.

- GET /workspaces — any authenticated user lists the workspaces they belong to.
- POST /admin/workspaces — org-admin creates a workspace.
- member CRUD under /admin/workspaces/{id}/members — workspace-admin (of that
  workspace) or org-admin.

Authority for the member endpoints is checked against the workspace in the PATH
(not the active-workspace header), and foreign workspaces return 404 so they are
indistinguishable from non-existent ones.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import events
from app.auth.middleware import get_current_user, require_role
from app.auth.router import limiter
from app.db import get_db
from app.db.models import User, Workspace, WorkspaceMembership, WorkspaceRole
from app.services import workspace_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["workspaces"])


class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class CreateWorkspaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str | None = Field(None, max_length=120)


class MemberOut(BaseModel):
    user_id: str
    email: str
    role: str


class AddMemberIn(BaseModel):
    user_id: str
    role: WorkspaceRole = WorkspaceRole.member


class SetRoleIn(BaseModel):
    role: WorkspaceRole


def _require_workspace_admin_path(
    db: Session, user: User, workspace_id: str
) -> Workspace:
    """Return the workspace if the user may administer it, else 404."""
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not workspace_service.is_workspace_admin(db, user, workspace_id):
        # Hide existence from non-admins of this workspace.
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/workspaces", response_model=list[WorkspaceOut])
@limiter.limit("100/minute")
def list_my_workspaces(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceOut]:
    """Workspaces the current user belongs to, with their role in each."""
    ids = workspace_service.list_workspace_ids_for_user(db, current_user)
    if not ids:
        return []
    workspaces = db.query(Workspace).filter(Workspace.id.in_(ids)).all()
    out: list[WorkspaceOut] = []
    for ws in workspaces:
        role = workspace_service.user_workspace_role(db, str(current_user.id), str(ws.id))
        role_value = (
            WorkspaceRole.workspace_admin.value
            if workspace_service.is_org_admin(current_user)
            else (role.value if role is not None else WorkspaceRole.member.value)
        )
        out.append(
            WorkspaceOut(id=str(ws.id), name=str(ws.name), slug=str(ws.slug), role=role_value)
        )
    return out


@router.post("/admin/workspaces", response_model=WorkspaceOut, status_code=201)
@limiter.limit("60/minute")
def create_workspace(
    request: Request,
    body: CreateWorkspaceIn,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    """Create a workspace (org-admin only). The creator becomes a workspace_admin."""
    ws = workspace_service.create_workspace(
        db, name=body.name, slug=body.slug, created_by=str(current_user.id), commit=False
    )
    workspace_service.add_member(
        db,
        workspace_id=ws.id,
        user_id=str(current_user.id),
        role=WorkspaceRole.workspace_admin,
        commit=False,
    )
    events.record_audit_event(
        db,
        action_type=events.WORKSPACE_CREATED,
        user_id=str(current_user.id),
        workspace_id=str(ws.id),
        metadata={"name": body.name},
        commit=False,
    )
    db.commit()
    return WorkspaceOut(
        id=str(ws.id),
        name=str(ws.name),
        slug=str(ws.slug),
        role=WorkspaceRole.workspace_admin.value,
    )


@router.get("/admin/workspaces/{workspace_id}/members", response_model=list[MemberOut])
@limiter.limit("100/minute")
def list_members(
    request: Request,
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    _require_workspace_admin_path(db, current_user, workspace_id)
    rows = (
        db.query(WorkspaceMembership, User)
        .join(User, User.id == WorkspaceMembership.user_id)
        .filter(WorkspaceMembership.workspace_id == workspace_id)
        .all()
    )
    return [
        MemberOut(
            user_id=str(m.user_id),
            email=str(u.email),
            role=str(getattr(m.role, "value", m.role)),
        )
        for m, u in rows
    ]


@router.post("/admin/workspaces/{workspace_id}/members", status_code=201)
@limiter.limit("60/minute")
def add_member(
    request: Request,
    workspace_id: str,
    body: AddMemberIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _require_workspace_admin_path(db, current_user, workspace_id)
    if db.get(User, body.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    workspace_service.add_member(
        db, workspace_id=workspace_id, user_id=body.user_id, role=body.role, commit=False
    )
    events.record_audit_event(
        db,
        action_type=events.WORKSPACE_MEMBERSHIP_GRANTED,
        user_id=str(current_user.id),
        workspace_id=workspace_id,
        metadata={"member_id": body.user_id, "role": body.role.value},
        commit=False,
    )
    db.commit()
    return {"status": "ok"}


@router.patch("/admin/workspaces/{workspace_id}/members/{user_id}")
@limiter.limit("60/minute")
def set_member_role(
    request: Request,
    workspace_id: str,
    user_id: str,
    body: SetRoleIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _require_workspace_admin_path(db, current_user, workspace_id)
    workspace_service.set_member_role(
        db, workspace_id=workspace_id, user_id=user_id, role=body.role, commit=False
    )
    events.record_audit_event(
        db,
        action_type=events.WORKSPACE_ROLE_CHANGED,
        user_id=str(current_user.id),
        workspace_id=workspace_id,
        metadata={"member_id": user_id, "role": body.role.value},
        commit=False,
    )
    db.commit()
    return {"status": "ok"}


@router.delete("/admin/workspaces/{workspace_id}/members/{user_id}", status_code=204)
@limiter.limit("60/minute")
def remove_member(
    request: Request,
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _require_workspace_admin_path(db, current_user, workspace_id)
    workspace_service.remove_member(db, workspace_id=workspace_id, user_id=user_id, commit=False)
    events.record_audit_event(
        db,
        action_type=events.WORKSPACE_MEMBERSHIP_REVOKED,
        user_id=str(current_user.id),
        workspace_id=workspace_id,
        metadata={"member_id": user_id},
        commit=False,
    )
    db.commit()
