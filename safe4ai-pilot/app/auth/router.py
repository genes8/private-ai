"""Authentication router: login, logout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.middleware import encode_token, get_current_user, hash_password, verify_password
from app.auth.oidc import (
    build_authorization_url,
    exchange_code_for_userinfo,
    load_oidc_config,
)
from app.config import settings
from app.db import get_db
from app.db.models import User, UserRole
from app.services.app_config_store import load_app_config

logger = structlog.get_logger(__name__)

# Module-level limiter — registered on app.state by main.py.
limiter: Limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])

_LOCK_THRESHOLD = 5
_LOCK_MINUTES = 30
_CSRF_COOKIE_NAME = "csrf_token"
_OIDC_STATE_COOKIE_NAME = "oidc_state"

_INVALID_CREDS_DETAIL = "Invalid credentials"


class LoginRequest(BaseModel):
    email: str
    password: str


def _clear_expired_lockout(user: User, *, now: datetime) -> bool:
    locked_until = user.locked_until
    if locked_until is None:
        return False
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    if locked_until > now:
        return False
    user.failed_login_count = 0
    user.locked_until = None
    return True


def _frontend_redirect_path() -> str:
    return settings.allowed_origins_list[0].rstrip("/") + "/chat"


def _set_session_cookies(response: Response, user: User, config: dict[str, object]) -> None:
    session_hours = int(config.get("session_hours", 24) or 24)
    cookie_max_age = session_hours * 60 * 60
    token = encode_token(str(user.id), str(user.role), expiry_hours=session_hours)
    csrf_token = secrets.token_urlsafe(32)

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


def _email_domain_allowed(email: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return True
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in allowed_domains


@router.get("/csrf")
async def get_csrf_token(response: Response) -> dict[str, str]:
    """Issue a pre-login CSRF token.  Call this before POST /auth/login."""
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=_CSRF_COOKIE_NAME,
        value=token,
        max_age=300,
        httponly=False,
        samesite="strict",
        secure=settings.enforce_https,
    )
    return {"csrf_token": token}


@router.get("/sso/status")
async def sso_status(db: Session = Depends(get_db)) -> dict[str, object]:
    """Return public OIDC login availability without exposing secrets."""
    config = load_app_config(db)
    oidc = load_oidc_config(config)
    return {
        "enabled": oidc.enabled,
        "configured": oidc.configured,
        "ssoOnly": bool(config.get("sso_only", False)),
        "loginUrl": "/auth/sso/start" if oidc.configured else None,
    }


@router.get("/sso/start")
@limiter.limit("20/minute")
async def sso_start(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    """Start OIDC authorization-code login."""
    config = load_app_config(db)
    oidc = load_oidc_config(config)
    if not oidc.configured:
        raise HTTPException(status_code=404, detail="SSO is not configured")

    state = secrets.token_urlsafe(32)
    try:
        authorize_url = await build_authorization_url(oidc, state)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OIDC provider unavailable") from exc

    response = RedirectResponse(authorize_url, status_code=302)
    response.set_cookie(
        key=_OIDC_STATE_COOKIE_NAME,
        value=state,
        max_age=300,
        httponly=True,
        samesite="lax",
        secure=settings.enforce_https,
    )
    return response


@router.get("/sso/callback")
@limiter.limit("20/minute")
async def sso_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Complete OIDC authorization-code login and issue app session cookies."""
    expected_state = request.cookies.get(_OIDC_STATE_COOKIE_NAME)
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status_code=403, detail="Invalid SSO state")

    config = load_app_config(db)
    oidc = load_oidc_config(config)
    if not oidc.configured:
        raise HTTPException(status_code=404, detail="SSO is not configured")

    try:
        userinfo = await exchange_code_for_userinfo(oidc, code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="OIDC login failed") from exc

    email = str(userinfo.get("email", "")).strip().lower()
    email_verified = bool(userinfo.get("email_verified", True))
    if not email or not email_verified:
        raise HTTPException(status_code=403, detail="OIDC email is not verified")
    if not _email_domain_allowed(email, oidc.allowed_domains):
        raise HTTPException(status_code=403, detail="OIDC email domain is not allowed")

    user: User | None = db.query(User).filter(User.email == email).first()
    if user is None:
        if not oidc.auto_provision:
            raise HTTPException(status_code=403, detail="User is not provisioned")
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.pilot_user,
            is_active=True,
            failed_login_count=0,
            locked_until=None,
        )
        db.add(user)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    user.failed_login_count = 0
    user.locked_until = None
    db.commit()

    response = RedirectResponse(_frontend_redirect_path(), status_code=302)
    _set_session_cookies(response, user, config)
    response.set_cookie(
        key=_OIDC_STATE_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        samesite="lax",
        secure=settings.enforce_https,
    )
    logger.info("user_sso_login_success", user_id=user.id)
    return response


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Authenticate a user and set an HTTP-Only JWT cookie."""
    config = load_app_config(db)
    oidc = load_oidc_config(config)
    if bool(config.get("sso_only", False)) and oidc.configured:
        raise HTTPException(status_code=403, detail="Password login is disabled by SSO policy")

    user: User | None = db.query(User).filter(User.email == body.email).first()

    # --- Brute-force protection ---
    if user is not None:
        now = datetime.now(UTC)
        lockout_cleared = _clear_expired_lockout(user, now=now)
        if (
            user.failed_login_count is not None
            and user.failed_login_count >= _LOCK_THRESHOLD
            and user.locked_until is not None
        ):
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=UTC)
            if locked_until > now:
                raise HTTPException(status_code=429, detail="Account temporarily locked")
        if lockout_cleared:
            db.commit()

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
    user.locked_until = None
    db.commit()

    response = Response(
        content='{"message": "logged in"}',
        media_type="application/json",
        status_code=200,
    )
    _set_session_cookies(response, user, config)
    logger.info("user_login_success", user_id=user.id)
    return response


@router.post("/logout")
async def logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Clear the JWT cookie and revoke the current token server-side."""
    current_user.token_valid_after = datetime.now(UTC)
    db.commit()
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
