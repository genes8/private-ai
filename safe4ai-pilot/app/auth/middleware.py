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
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=expiry_hours),
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

    return user


def require_role(role: str) -> Callable[..., User]:
    """Return a FastAPI dependency that enforces a specific role."""

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user

    return _check
