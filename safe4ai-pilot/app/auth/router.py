"""Authentication router: login, logout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth.middleware import encode_token, verify_password
from app.config import settings
from app.db import get_db
from app.db.models import User
from app.services.app_config_store import load_app_config

logger = structlog.get_logger(__name__)

# Module-level limiter — registered on app.state by main.py.
limiter: Limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])

_LOCK_THRESHOLD = 20
_LOCK_MINUTES = 15
_CSRF_COOKIE_NAME = "csrf_token"
_MIN_PASSWORD_LENGTH = 12

_INVALID_CREDS_DETAIL = "Invalid credentials"


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Authenticate a user and set an HTTP-Only JWT cookie."""
    # Server-side password length check
    if len(body.password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=401, detail=_INVALID_CREDS_DETAIL)

    user: User | None = db.query(User).filter(User.email == body.email).first()

    # --- Brute-force protection ---
    if user is not None:
        if (
            user.failed_login_count is not None
            and user.failed_login_count >= _LOCK_THRESHOLD
            and user.locked_until is not None
        ):
            now = datetime.now(UTC)
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=UTC)
            if locked_until > now:
                raise HTTPException(status_code=429, detail="Account temporarily locked")

    # --- Credential verification (always, to prevent timing attacks) ---
    password_ok = False
    if user is not None and user.is_active:
        password_ok = verify_password(body.password, str(user.password_hash))

    if not password_ok:
        # Increment failure counter (if user exists)
        if user is not None:
            count = (user.failed_login_count or 0) + 1
            user.failed_login_count = count
            if count >= _LOCK_THRESHOLD:
                user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCK_MINUTES)
                logger.warning("account_locked", user_id=user.id)
            db.commit()

        raise HTTPException(status_code=401, detail=_INVALID_CREDS_DETAIL)

    # --- Success ---
    assert user is not None  # noqa: S101  # guaranteed: password_ok=True requires user is not None
    user.failed_login_count = 0
    db.commit()

    config = load_app_config(db)
    session_hours = int(config.get("session_hours", 24) or 24)
    cookie_max_age = session_hours * 60 * 60
    token = encode_token(str(user.id), str(user.role), expiry_hours=session_hours)
    csrf_token = secrets.token_urlsafe(32)

    response = Response(
        content='{"message": "logged in"}',
        media_type="application/json",
        status_code=200,
    )
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=cookie_max_age,
        httponly=True,
        samesite="strict",
        secure=settings.enforce_https,
    )
    response.set_cookie(
        key=_CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=cookie_max_age,
        httponly=False,
        samesite="strict",
        secure=settings.enforce_https,
    )
    logger.info("user_login_success", user_id=user.id)
    return response


@router.post("/logout")
async def logout() -> Response:
    """Clear the JWT cookie."""
    response = Response(
        content='{"message": "logged out"}',
        media_type="application/json",
        status_code=200,
    )
    response.set_cookie(
        key="access_token",
        value="",
        max_age=0,
        httponly=True,
        samesite="strict",
        secure=settings.enforce_https,
    )
    response.set_cookie(
        key=_CSRF_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=False,
        samesite="strict",
        secure=settings.enforce_https,
    )
    return response
