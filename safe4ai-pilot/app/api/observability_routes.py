from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user, require_role
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import FeedbackRating, User
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


@router.get("/admin/stats/cost")
@limiter.limit("100/minute")
async def cost_stats(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Return aggregate cost statistics for the given number of past days."""
    if days < 1 or days > 366:
        raise HTTPException(status_code=422, detail="days must be between 1 and 366")
    tracker = CostTracker(settings.cost_per_1k_tokens)
    return tracker.get_stats(db, days=days)
