"""Admin user management routes."""
from __future__ import annotations

import re
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.middleware import hash_password, require_role
from app.auth.password_policy import validate_password_strength
from app.auth.router import limiter
from app.db import get_db
from app.db.models import User, UserRole
from app.services.user_service import deactivate_user_cascade

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CreateUserRequest(BaseModel):
    email: str
    password: str | None = None
    role: UserRole = UserRole.pilot_user

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.fullmatch(v):
            raise ValueError("Invalid email format")
        return v


@router.get("/admin/users")
@limiter.limit("100/minute")
def list_users(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset cannot be negative")
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/admin/users", status_code=201)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    if body.password is None:
        raise HTTPException(status_code=422, detail="Password is required")
    validate_password_strength(body.password)
    existing = db.query(User).filter(User.email == body.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    logger.info("user_created", user_id=str(user.id), email=body.email, invited=False)
    return {"id": str(user.id)}


@router.delete("/admin/users/{user_id}", status_code=204)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("admin")),
) -> None:
    if user_id == str(current_admin.id):
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot deactivate admin users")
    deactivate_user_cascade(db, user)
    db.commit()
