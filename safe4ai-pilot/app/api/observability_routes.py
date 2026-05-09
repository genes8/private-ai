from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.middleware import require_role
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
async def submit_feedback(body: FeedbackRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Submit user feedback for a query response.

    Note: user_id will come from auth middleware in Phase 3A; hardcoded to 'anonymous' for now.
    """
    store = FeedbackStore(db)
    fid = store.store(body.session_id, "anonymous", body.trace_id, body.rating, body.comment)
    return {"id": fid}


@router.get("/admin/feedback")
async def list_feedback(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    """Return the most recent feedback entries (admin only)."""
    store = FeedbackStore(db)
    return store.list_for_admin(db)


@router.get("/admin/stats/cost")
async def cost_stats(
    days: int = 30,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Return aggregate cost statistics for the given number of past days."""
    tracker = CostTracker(settings.cost_per_1k_tokens)
    return tracker.get_stats(db, days=days)
