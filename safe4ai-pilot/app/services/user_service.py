"""User lifecycle helpers: ghost-user creation and deactivation cascade."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.middleware import hash_password
from app.db.models import (
    DELETED_USER_ID,
    AgentRun,
    AuditLog,
    Document,
    HumanReviewQueue,
    QueryFeedback,
    User,
    UserRole,
)
from app.db.models import Session as DbSession

logger = structlog.get_logger(__name__)

_DELETED_USER_ID = DELETED_USER_ID  # alias kept so call-sites below are unchanged
_DELETED_USER_EMAIL = "deleted@redacted.local"


def ensure_deleted_user(db: Session) -> User:
    """Return (and if necessary create) the sentinel ghost user for deleted accounts."""
    deleted_user = db.get(User, _DELETED_USER_ID)
    if deleted_user is not None:
        return deleted_user
    deleted_user = db.query(User).filter(User.email == _DELETED_USER_EMAIL).first()
    if deleted_user is not None:
        return deleted_user

    deleted_user = User(
        id=_DELETED_USER_ID,
        email=_DELETED_USER_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(24)),
        role=UserRole.pilot_user,
        is_active=False,
    )
    db.add(deleted_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(User).filter(User.email == _DELETED_USER_EMAIL).first()
        if existing is None:
            raise
        return existing
    return deleted_user


def deactivate_user_cascade(db: Session, user: User) -> None:
    """Reassign owned content to ghost user, strip PII, revoke sessions.

    Caller is responsible for calling db.commit() after this function returns.
    """
    user_id = str(user.id)
    deleted_user = ensure_deleted_user(db)

    db.query(Document).filter(Document.uploaded_by == user_id).update(
        {Document.uploaded_by: deleted_user.id},
        synchronize_session=False,
    )
    user_session_ids = [
        s.id for s in db.query(DbSession).filter(DbSession.user_id == user_id).all()
    ]
    if user_session_ids:
        db.query(AgentRun).filter(AgentRun.session_id.in_(user_session_ids)).delete(
            synchronize_session=False
        )
    db.query(DbSession).filter(DbSession.user_id == user_id).delete()
    db.query(QueryFeedback).filter(QueryFeedback.user_id == user_id).delete()
    db.query(HumanReviewQueue).filter(HumanReviewQueue.user_id == user_id).delete()
    db.query(AuditLog).filter(AuditLog.user_id == user_id).update(
        {AuditLog.user_id: None},
        synchronize_session=False,
    )

    user.is_active = False
    user.email = f"deactivated+{user.id}@redacted.local"
    user.password_hash = hash_password(secrets.token_urlsafe(24))
    user.failed_login_count = 0
    user.locked_until = None
    user.token_valid_after = datetime.now(UTC)
    logger.info("user_deactivated", user_id=user_id)
