from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AppConfig


def load_app_config(db: Session) -> dict[str, Any]:
    """Return all persisted app_config values as a flat key/value map."""
    return {row.key: row.value for row in db.query(AppConfig).all()}


def upsert_app_config(db: Session, updates: dict[str, Any], *, commit: bool = True) -> None:
    """Insert or update app_config rows for the provided keys."""
    for key, value in updates.items():
        row = db.get(AppConfig, key)
        if row is None:
            row = AppConfig(key=key, value=value)
            db.add(row)
        else:
            row.value = value
    if commit:
        db.commit()
