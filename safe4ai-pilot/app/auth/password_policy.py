from __future__ import annotations

from fastapi import HTTPException


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters")
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(not char.isalnum() for char in password)
    if not (has_upper and has_lower and has_digit and has_special):
        raise HTTPException(
            status_code=422,
            detail="Password must include uppercase, lowercase, digit, and special character",
        )
