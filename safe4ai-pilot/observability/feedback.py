from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.db.models import FeedbackRating, QueryFeedback

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
    ) -> str:
        """Insert a QueryFeedback row and return its UUID."""
        feedback_id = str(uuid.uuid4())
        feedback = QueryFeedback(
            id=feedback_id,
            trace_id=trace_id,
            session_id=session_id,
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

    def list_for_admin(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent feedback rows as plain dicts."""
        rows = (
            self._db.query(QueryFeedback)
            .order_by(QueryFeedback.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "session_id": r.session_id,
                "trace_id": r.trace_id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
