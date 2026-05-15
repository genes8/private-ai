from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.db.models import AppConfig

# Keys in this set are encrypted at rest using Fernet derived from SECRET_KEY.
_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "openai_api_key",
    "anthropic_api_key",
    "api_key",
})

_CIPHER_PREFIX = "enc:"


def _get_fernet(secret_key: str) -> Fernet:
    raw = hashlib.sha256(secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def _encrypt(value: str, secret_key: str) -> str:
    return _CIPHER_PREFIX + _get_fernet(secret_key).encrypt(value.encode()).decode()


def _decrypt(value: str, secret_key: str) -> str:
    if not isinstance(value, str) or not value.startswith(_CIPHER_PREFIX):
        return value
    try:
        return _get_fernet(secret_key).decrypt(value[len(_CIPHER_PREFIX):].encode()).decode()
    except InvalidToken:
        return value


def load_app_config(db: Session) -> dict[str, Any]:
    """Return all persisted app_config values as a flat key/value map.

    Sensitive keys are transparently decrypted on read.
    """
    from app.config import settings  # local import to avoid circular dep at module load

    result: dict[str, Any] = {}
    for row in db.query(AppConfig).all():
        if row.key in _SENSITIVE_KEYS and isinstance(row.value, str):
            result[row.key] = _decrypt(row.value, settings.secret_key)
        else:
            result[row.key] = row.value
    return result


def upsert_app_config(db: Session, updates: dict[str, Any], *, commit: bool = True) -> None:
    """Insert or update app_config rows.

    Sensitive keys are encrypted before writing.
    """
    from app.config import settings  # local import to avoid circular dep at module load

    for key, value in updates.items():
        stored_value: Any = value
        if key in _SENSITIVE_KEYS and isinstance(value, str):
            stored_value = _encrypt(value, settings.secret_key)
        row = db.get(AppConfig, key)
        if row is None:
            row = AppConfig(key=key, value=stored_value)
            db.add(row)
        else:
            row.value = stored_value
    if commit:
        db.commit()
