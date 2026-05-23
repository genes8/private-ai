from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user, require_role
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import AuditLog, FeedbackRating, QueryFeedback, User
from observability.cost_tracker import CostTracker
from observability.feedback import FeedbackStore

router = APIRouter(tags=["observability"])


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
    """Submit user feedback for a query response."""
    store = FeedbackStore(db)
    fid = store.store(body.session_id, str(current_user.id), body.trace_id, body.rating, body.comment)
    return {"id": fid}


@router.get("/admin/feedback")
@limiter.limit("100/minute")
async def list_feedback(
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    """Return the most recent feedback entries (admin only)."""
    store = FeedbackStore(db)
    return store.list_for_admin()


@router.get("/admin/feedback/count")
@limiter.limit("120/minute")
async def feedback_count(
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, int]:
    """Lightweight negative-feedback count for the sidebar badge."""
    from sqlalchemy import func as sqlfunc

    negative = (
        db.query(sqlfunc.count(QueryFeedback.id))
        .filter(QueryFeedback.rating == FeedbackRating.negative)
        .scalar()
        or 0
    )
    return {"negative": int(negative)}


@router.get("/admin/feedback/{feedback_id}/trace")
@limiter.limit("100/minute")
async def get_feedback_trace(
    request: Request,
    feedback_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Return audit log trace data for a specific feedback item."""
    feedback = db.query(QueryFeedback).filter(QueryFeedback.id == feedback_id).first()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.trace_id == feedback.trace_id)
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    if audit is None:
        return {"found": False, "traceId": feedback.trace_id}
    return {
        "found": True,
        "traceId": audit.trace_id,
        "latencyMs": audit.latency_ms,
        "modelUsed": audit.model_used,
        "timestamp": audit.timestamp.isoformat() if audit.timestamp else None,
        "actionType": audit.action_type,
        "cacheHit": (audit.response_metadata or {}).get("cache_hit", False),
    }


@router.get("/admin/stats/cost")
@limiter.limit("100/minute")
async def cost_stats(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Return detailed cost statistics broken down by day (no frontend consumer).

    Intentionally kept for external dashboards, billing integrations, and
    operators who want per-day cost data beyond the summary in /admin/stats.
    """
    if days < 1 or days > 366:
        raise HTTPException(status_code=422, detail="days must be between 1 and 366")
    tracker = CostTracker(settings.cost_per_1k_tokens)
    return tracker.get_stats(db, days=days)
