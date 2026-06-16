"""Tier quota enforcement: seat cap, monthly query cap, evaluation expiry.

All checks raise domain exceptions — callers are responsible for mapping
them to HTTP responses. No FastAPI dependency in this module.

WORKSPACE SCOPE (decision): quota enforcement is **instance-wide**, NOT
per-workspace. Seats and the monthly query cap are a per-deployment commercial
contract (one company = one deployment); workspaces are an internal org-chart
concept, not a billing boundary. Per-workspace counters below exist only for
admin dashboards and must never gate requests.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions (mirror CostCeilingExceeded pattern from cost_service.py)
# ---------------------------------------------------------------------------


class SeatLimitExceeded(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


class QuotaExceeded(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


class TierExpired(Exception):
    """Raised when the evaluation period has passed its expiry date."""
    def __init__(self, detail: str) -> None:
        self.detail = detail


# ---------------------------------------------------------------------------
# Read-side counters (shared by enforcement checks AND settings serialization)
# ---------------------------------------------------------------------------


def count_active_seats(db: Session) -> int:
    """Return the number of active non-sentinel users.

    Used by both check_seat_limit() (enforcement) and serialize_settings()
    (display). Keeping the logic here means a single source of truth —
    the admin UI and the enforcement gate always agree.
    """
    from app.db.models import DELETED_USER_ID, User

    return (
        db.query(User)
        .filter(User.is_active == True, User.id != DELETED_USER_ID)  # noqa: E712
        .count()
    )


def count_monthly_queries(db: Session) -> int:
    """Return the number of chat_query AuditLog rows in the current calendar month.

    KNOWN LIMITATION: The stream path finalises the AuditLog entry
    asynchronously after the response is sent, so the count can lag by
    ~1 query. Do not use this as a hard billing gate without replacing the
    AuditLog count with a dedicated transactional usage ledger.
    """
    from app.db.models import AuditLog

    start_of_month = datetime.now(UTC).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.action_type == "chat_query",
            AuditLog.timestamp >= start_of_month,
        )
        .count()
    )


def count_workspace_queries(db: Session, workspace_id: str) -> int:
    """Read-only chat_query count for one workspace this calendar month.

    Display/dashboard only — this is NOT an enforcement gate (quotas are
    instance-wide; see the module docstring).
    """
    from app.db.models import AuditLog

    start_of_month = datetime.now(UTC).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.action_type == "chat_query",
            AuditLog.workspace_id == workspace_id,
            AuditLog.timestamp >= start_of_month,
        )
        .count()
    )


# ---------------------------------------------------------------------------
# Enforcement helpers
# ---------------------------------------------------------------------------


def check_seat_limit(db: Session, config: dict[str, Any]) -> None:
    """Raise SeatLimitExceeded if adding a new user would exceed max_seats.

    ``max_seats == 0`` means unlimited (Team / Enterprise).
    """
    max_seats = int(config.get("max_seats", 0))
    if max_seats == 0:
        return

    active_count = count_active_seats(db)
    if active_count >= max_seats:
        tier = config.get("tier", "evaluation")
        raise SeatLimitExceeded(
            f"Seat limit reached ({active_count}/{max_seats} seats on {tier} tier)"
        )


def check_query_quota(db: Session, config: dict[str, Any]) -> None:
    """Raise QuotaExceeded if the monthly query count has reached its cap.

    Called BEFORE LLM invocation (preflight).
    ``monthly_query_limit == 0`` means unlimited (Team / Enterprise).
    """
    limit = int(config.get("monthly_query_limit", 0))
    if limit == 0:
        return

    count = count_monthly_queries(db)
    if count >= limit:
        tier = config.get("tier", "evaluation")
        raise QuotaExceeded(
            f"Monthly query limit reached ({count}/{limit} queries on {tier} tier)"
        )


def check_tier_expiry(config: dict[str, Any]) -> None:
    """Raise TierExpired if the evaluation period has passed its expiry date.

    Only ``tier == "evaluation"`` has an expiry model. Team and Enterprise
    deployments are not subject to expiry, even if a stale ``tier_expires_at``
    value remains from a previous evaluation period. This prevents a realistic
    upgrade path (set tier=team, forget to clear tier_expires_at) from locking
    out a paid deployment until the date is manually cleared.

    Callers must map TierExpired → HTTPException(403) so this module stays
    free of FastAPI dependencies.
    """
    tier = config.get("tier", "evaluation")
    if tier != "evaluation":
        return  # team / enterprise tiers do not expire

    expires_raw = config.get("tier_expires_at")
    if not expires_raw:
        return

    parsed = datetime.fromisoformat(expires_raw)
    # If the stored string is naive (no tzinfo), assume UTC.
    # If it already carries a timezone offset, convert to UTC via
    # .astimezone() — do NOT use .replace() which would silently overwrite
    # an existing offset with a wrong UTC value.
    if parsed.tzinfo is None:
        expires: datetime = parsed.replace(tzinfo=UTC)
    else:
        expires = parsed.astimezone(UTC)

    if datetime.now(UTC) > expires:
        logger.info("tier_expiry_blocked", tier_expires_at=expires_raw)
        raise TierExpired("Evaluation period has expired. Contact us to upgrade.")
