from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user, hash_password, verify_password
from app.auth.password_policy import validate_password_strength
from app.db import get_db
from app.db.models import (
    AuditLog,
    FeedbackRating,
    QueryFeedback,
    User,
)
from app.services.app_config_store import load_app_config
from app.services.stats_service import get_corpus_stats

router = APIRouter(prefix="/account", tags=["account"])
me_router = APIRouter(tags=["account"])


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


@router.get("/settings")
def get_account_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    config = load_app_config(db)
    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    questions_7d = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.user_id == current_user.id)
        .filter(AuditLog.action_type == "chat_query")
        .filter(AuditLog.timestamp >= seven_days_ago)
        .scalar()
        or 0
    )
    questions_30d = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.user_id == current_user.id)
        .filter(AuditLog.action_type == "chat_query")
        .filter(AuditLog.timestamp >= thirty_days_ago)
        .scalar()
        or 0
    )
    feedback_positive = (
        db.query(func.count(QueryFeedback.id))
        .filter(QueryFeedback.user_id == current_user.id)
        .filter(QueryFeedback.rating == FeedbackRating.positive)
        .scalar()
        or 0
    )
    feedback_negative = (
        db.query(func.count(QueryFeedback.id))
        .filter(QueryFeedback.user_id == current_user.id)
        .filter(QueryFeedback.rating == FeedbackRating.negative)
        .scalar()
        or 0
    )
    last_activity_at = (
        db.query(func.max(AuditLog.timestamp))
        .filter(AuditLog.user_id == current_user.id)
        .filter(AuditLog.action_type == "chat_query")
        .scalar()
    )

    corpus = get_corpus_stats(db)

    role = getattr(current_user.role, "value", current_user.role)
    return {
        "profile": {
            "id": str(current_user.id),
            "email": current_user.email,
            "role": role,
            "isActive": bool(current_user.is_active),
            "createdAt": current_user.created_at,
        },
        "security": {
            "sessionHours": int(config.get("session_hours", 24) or 24),
            "ssoOnly": bool(config.get("sso_only", False)),
            "passwordChangeAllowed": not bool(config.get("sso_only", False)),
        },
        "usage": {
            "questions7d": questions_7d,
            "questions30d": questions_30d,
            "feedbackPositive": feedback_positive,
            "feedbackNegative": feedback_negative,
            "lastActivityAt": last_activity_at,
        },
        "knowledgeBase": corpus,
    }


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    config = load_app_config(db)
    if bool(config.get("sso_only", False)):
        raise HTTPException(status_code=403, detail="Password changes are disabled for SSO-only mode")
    if not verify_password(body.currentPassword, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    validate_password_strength(body.newPassword)
    current_user.password_hash = hash_password(body.newPassword)
    current_user.token_valid_after = datetime.now(UTC)
    db.commit()
    return {"message": "Password changed. Please sign in again with your new password."}


@me_router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Return profile info for the currently authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
