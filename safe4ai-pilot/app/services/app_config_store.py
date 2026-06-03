from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.db.models import AppConfig

# Expected Python types for known config keys. Values read from the DB are coerced
# to these types so that callers can rely on consistent types even if the JSON value
# was written as a string (e.g., via a direct DB edit).
_KEY_TYPES: dict[str, type] = {
    "audit_retention_days": int,
    "session_hours": int,
    "retrieval_k": int,
    "chunk_size": int,
    "chunk_overlap": int,
    "daily_ceiling_usd": float,
    "monthly_ceiling_usd": float,
    "score_floor": float,
    "reranker_enabled": bool,
    "sso_only": bool,
    "redact_pii": bool,
    "oidc_enabled": bool,
    "oidc_issuer_url": str,
    "oidc_client_id": str,
    "oidc_redirect_uri": str,
    "oidc_allowed_domains": list,
    "oidc_auto_provision": bool,
    # Tier / license config
    "tier": str,                  # "evaluation" | "team" | "enterprise"
    "max_seats": int,             # 0 = unlimited
    "monthly_query_limit": int,   # 0 = unlimited
    "tier_expires_at": str,       # ISO-8601 UTC string; absent/empty = no expiry
    "blocked_terms": list,
    "provider_resolved_ip": str,
}

# Keys in this set are encrypted at rest using Fernet derived from SECRET_KEY.
_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "openai_api_key",
    "anthropic_api_key",
    "api_key",
    "provider_api_key",
    "oidc_client_secret",
})

_CIPHER_PREFIX = "enc:"
_TRUE_STRINGS = {"1", "true", "yes", "on"}
_FALSE_STRINGS = {"0", "false", "no", "off", ""}


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


def _coerce_value(value: Any, expected: type) -> Any:
    if expected is list:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            raise ValueError(f"Invalid list JSON: {value}")
        return list(value)
    if expected is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUE_STRINGS:
                return True
            if normalized in _FALSE_STRINGS:
                return False
            raise ValueError(f"Invalid boolean string: {value}")
        return bool(value)
    if isinstance(value, expected):
        return value
    return expected(value)


def load_app_config(db: Session) -> dict[str, Any]:
    """Return all persisted app_config values as a flat key/value map.

    Sensitive keys are transparently decrypted on read.
    """
    from app.config import settings  # local import to avoid circular dep at module load

    result: dict[str, Any] = {}
    for row in db.query(AppConfig).all():
        if row.key in _SENSITIVE_KEYS and isinstance(row.value, str):
            value: Any = _decrypt(row.value, settings.secret_key)
        else:
            value = row.value
        if row.key in _KEY_TYPES:
            try:
                expected = _KEY_TYPES[row.key]
                value = _coerce_value(value, expected)
            except (TypeError, ValueError):
                pass
        result[row.key] = value
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
