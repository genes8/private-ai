from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AuditLog, FeedbackRating, QueryFeedback, User

logger = structlog.get_logger(__name__)

__all__ = ["FeedbackRating", "FeedbackStore"]


class FeedbackStore:
    """Persist and retrieve user feedback on query responses."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def store(
        self,
        session_id: str,
        user_id: str,
        trace_id: str,
        rating: FeedbackRating,
        comment: str | None = None,
        workspace_id: str | None = None,
    ) -> str:
        """Insert a QueryFeedback row and return its UUID."""
        feedback_id = str(uuid.uuid4())
        feedback = QueryFeedback(
            id=feedback_id,
            trace_id=trace_id,
            session_id=session_id,
            workspace_id=workspace_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
        )
        self._db.add(feedback)
        self._db.commit()
        logger.info(
            "feedback_stored",
            feedback_id=feedback_id,
            session_id=session_id,
            trace_id=trace_id,
            rating=rating,
        )
        return feedback_id

    def list_for_admin(
        self, limit: int = 100, workspace_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return the most recent feedback rows as plain dicts (optionally scoped)."""
        effective_limit = max(1, min(limit, 1000))
        q = self._db.query(QueryFeedback)
        if workspace_ids is not None:
            q = q.filter(QueryFeedback.workspace_id.in_(workspace_ids))
        rows = q.order_by(QueryFeedback.created_at.desc()).limit(effective_limit).all()
        user_ids = {r.user_id for r in rows if r.user_id}
        user_rows = (
            self._db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        )
        user_emails = {str(user.id): user.email for user in user_rows}
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_email": user_emails.get(str(r.user_id)),
                "session_id": r.session_id,
                "trace_id": r.trace_id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def count_negative(self, workspace_ids: list[str] | None = None) -> int:
        """Return the total count of negative feedback entries (optionally scoped)."""
        q = self._db.query(func.count(QueryFeedback.id)).filter(
            QueryFeedback.rating == FeedbackRating.negative
        )
        if workspace_ids is not None:
            q = q.filter(QueryFeedback.workspace_id.in_(workspace_ids))
        return int(q.scalar() or 0)

    def get_trace(
        self, feedback_id: str, workspace_ids: list[str] | None = None
    ) -> dict[str, Any] | None:
        """Return audit trace data for a feedback item, or None if not found/foreign."""
        q = self._db.query(QueryFeedback).filter(QueryFeedback.id == feedback_id)
        if workspace_ids is not None:
            q = q.filter(QueryFeedback.workspace_id.in_(workspace_ids))
        feedback = q.first()
        if feedback is None:
            return None
        audit = (
            self._db.query(AuditLog)
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
