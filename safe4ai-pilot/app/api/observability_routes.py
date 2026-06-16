from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import AuditLog, FeedbackRating, User
from app.db.models import Session as DbSession
from observability.cost_tracker import CostTracker
from observability.feedback import FeedbackStore

router = APIRouter(tags=["observability"])


def _admin_scope(db: Session, user: User) -> list[str] | None:
    """Workspace scope for admin observability views (org-admin ⇒ None)."""
    from app.services import workspace_service

    try:
        return workspace_service.admin_workspace_scope(db, user)
    except workspace_service.WorkspaceAccessDenied:
        raise HTTPException(status_code=403, detail="Forbidden")


class FeedbackRequest(BaseModel):
    session_id: str
    trace_id: str
    rating: FeedbackRating
    comment: str | None = None


@router.post("/feedback")
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Submit user feedback for a query response.

    Anti-IDOR: the session must belong to the caller and the trace must belong to
    that session, otherwise 404 — a user cannot attach feedback to someone else's
    trace/session by guessing an id. The feedback inherits the session's workspace.
    """
    session_row = db.get(DbSession, body.session_id)
    if session_row is None or str(session_row.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    trace_owned = (
        db.query(AuditLog.id)
        .filter(AuditLog.trace_id == body.trace_id, AuditLog.session_id == body.session_id)
        .first()
    )
    if trace_owned is None:
        raise HTTPException(status_code=404, detail="Trace not found for session")
    store = FeedbackStore(db)
    fid = store.store(
        body.session_id,
        str(current_user.id),
        body.trace_id,
        body.rating,
        body.comment,
        workspace_id=session_row.workspace_id,
    )
    return {"id": fid}


@router.get("/admin/feedback")
@limiter.limit("100/minute")
async def list_feedback(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return the most recent feedback entries, scoped to the admin's workspaces."""
    scope = _admin_scope(db, current_user)
    return FeedbackStore(db).list_for_admin(workspace_ids=scope)


@router.get("/admin/feedback/count")
@limiter.limit("120/minute")
async def feedback_count(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Lightweight negative-feedback count for the sidebar badge."""
    scope = _admin_scope(db, current_user)
    return {"negative": FeedbackStore(db).count_negative(workspace_ids=scope)}


@router.get("/admin/feedback/{feedback_id}/trace")
@limiter.limit("100/minute")
async def get_feedback_trace(
    request: Request,
    feedback_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return audit log trace data for a specific feedback item (workspace-scoped)."""
    scope = _admin_scope(db, current_user)
    trace = FeedbackStore(db).get_trace(feedback_id, workspace_ids=scope)
    if trace is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return trace


@router.get("/admin/stats/cost")
@limiter.limit("100/minute")
async def cost_stats(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return detailed cost statistics broken down by day (no frontend consumer).

    Intentionally kept for external dashboards, billing integrations, and
    operators who want per-day cost data beyond the summary in /admin/stats.
    """
    if days < 1 or days > 366:
        raise HTTPException(status_code=422, detail="days must be between 1 and 366")
    scope = _admin_scope(db, current_user)
    tracker = CostTracker(settings.cost_per_1k_tokens)
    return tracker.get_stats(db, days=days, workspace_ids=scope)
