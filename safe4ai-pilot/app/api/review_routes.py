"""Admin human review queue routes."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.middleware import require_role
from app.auth.router import limiter
from app.db import get_db
from app.db.models import HumanReviewQueue, ReviewStatus, User
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])


@router.get("/admin/review-queue")
@limiter.limit("100/minute")
def list_review_queue(
    request: Request,
    status: ReviewStatus = ReviewStatus.pending,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    rows = (
        db.query(HumanReviewQueue)
        .filter(HumanReviewQueue.status == status)
        .order_by(HumanReviewQueue.id)
        .all()
    )
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "user_id": r.user_id,
            "query": r.query,
            "draft_answer": r.draft_answer,
            "risk_reason": r.risk_reason,
            "status": r.status,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at,
        }
        for r in rows
    ]


@router.post("/admin/review-queue/{item_id}/approve", status_code=200)
def approve_review_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    item = db.get(HumanReviewQueue, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != ReviewStatus.pending:
        raise HTTPException(status_code=409, detail="Item already reviewed")
    item.status = ReviewStatus.approved
    item.reviewed_by = str(current_admin.id)
    item.reviewed_at = datetime.now(UTC)
    db.commit()
    return {"status": "approved"}


@router.post("/admin/review-queue/{item_id}/reject", status_code=200)
def reject_review_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    item = db.get(HumanReviewQueue, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != ReviewStatus.pending:
        raise HTTPException(status_code=409, detail="Item already reviewed")
    item.status = ReviewStatus.rejected
    item.reviewed_by = str(current_admin.id)
    item.reviewed_at = datetime.now(UTC)
    db.commit()
    return {"status": "rejected"}
