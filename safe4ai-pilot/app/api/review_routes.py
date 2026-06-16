"""Admin human review queue routes."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user
from app.auth.router import limiter
from app.db import get_db
from app.db.models import HumanReviewQueue, ReviewStatus, User

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])


def _review_scope(db: Session, user: User) -> list[str] | None:
    """Workspace scope for the review queue (org-admin ⇒ None ⇒ unrestricted)."""
    from app.services import workspace_service

    try:
        return workspace_service.admin_workspace_scope(db, user)
    except workspace_service.WorkspaceAccessDenied:
        raise HTTPException(status_code=403, detail="Forbidden")


def _authorize_review_item(db: Session, user: User, item_id: str) -> HumanReviewQueue:
    """Load a review item the user may act on, else 404 (foreign-workspace safe)."""
    from app.services import workspace_service

    item = db.get(HumanReviewQueue, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if not workspace_service.is_org_admin(user):
        ws_id = item.workspace_id
        if ws_id is None or not workspace_service.is_workspace_admin(db, user, str(ws_id)):
            raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.get("/admin/review-queue")
@limiter.limit("100/minute")
def list_review_queue(
    request: Request,
    status: ReviewStatus = ReviewStatus.pending,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    scope = _review_scope(db, current_user)
    q = db.query(HumanReviewQueue).filter(HumanReviewQueue.status == status)
    if scope is not None:
        q = q.filter(HumanReviewQueue.workspace_id.in_(scope))
    rows = q.order_by(HumanReviewQueue.id).all()
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
    current_admin: User = Depends(get_current_user),
) -> dict[str, str]:
    item = _authorize_review_item(db, current_admin, item_id)
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
    current_admin: User = Depends(get_current_user),
) -> dict[str, str]:
    item = _authorize_review_item(db, current_admin, item_id)
    if item.status != ReviewStatus.pending:
        raise HTTPException(status_code=409, detail="Item already reviewed")
    item.status = ReviewStatus.rejected
    item.reviewed_by = str(current_admin.id)
    item.reviewed_at = datetime.now(UTC)
    db.commit()
    return {"status": "rejected"}
