"""JWT auth, RBAC, password hashing utilities."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
import structlog
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.db.models import User

logger = structlog.get_logger(__name__)

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 8


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def encode_token(user_id: str, role: str, *, expiry_hours: int = JWT_EXPIRY_HOURS) -> str:
    """Create a signed JWT for the given user."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": now.timestamp(),
        "exp": now + timedelta(hours=expiry_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT, raising jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: extract JWT from cookie and return the active User."""
    token: str | None = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        logger.warning("invalid_jwt_token")
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id: str = payload.get("sub", "")
    user: User | None = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token_role = payload.get("role")
    current_role = getattr(user.role, "value", user.role)
    normalized_token_role = str(token_role).split(".")[-1] if token_role else ""
    if normalized_token_role and normalized_token_role != str(current_role):
        logger.warning(
            "stale_jwt_role",
            user_id=user_id,
            token_role=normalized_token_role,
            db_role=str(current_role),
        )
        raise HTTPException(status_code=401, detail="Not authenticated")
    token_iat = payload.get("iat")
    valid_after = getattr(user, "token_valid_after", None)
    if isinstance(valid_after, datetime):
        if valid_after.tzinfo is None:
            valid_after = valid_after.replace(tzinfo=UTC)
        issued_at: datetime | None = None
        if isinstance(token_iat, (int, float)):
            issued_at = datetime.fromtimestamp(token_iat, tz=UTC)
        elif isinstance(token_iat, datetime):
            issued_at = token_iat if token_iat.tzinfo is not None else token_iat.replace(tzinfo=UTC)
        if issued_at is not None and issued_at <= valid_after:
            logger.warning("revoked_jwt_token", user_id=user_id)
            raise HTTPException(status_code=401, detail="Not authenticated")

    return user


def require_role(role: str) -> Callable[..., User]:
    """Return a FastAPI dependency that enforces a specific role."""
    normalized_role = str(role).split(".")[-1]

    def _check(current_user: User = Depends(get_current_user)) -> User:
        current_role = str(getattr(current_user.role, "value", current_user.role))
        if current_role != normalized_role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user

    return _check
