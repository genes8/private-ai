"""Unit tests for app.services.quota_service.

Covers: seat cap, monthly query cap, tier expiry helpers.
Endpoint-level smoke tests live in test_admin.py.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.quota_service import (
    QuotaExceeded,
    SeatLimitExceeded,
    TierExpired,
    check_query_quota,
    check_seat_limit,
    check_tier_expiry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DELETED_USER_ID = "00000000-0000-0000-0000-000000000001"


def _db_with_active_user_count(count: int) -> MagicMock:
    """Return a mock DB whose User query returns *count* active seats."""
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = count
    return db


def _db_with_audit_count(count: int) -> MagicMock:
    """Return a mock DB whose AuditLog query returns *count* rows."""
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = count
    return db


# ---------------------------------------------------------------------------
# check_seat_limit
# ---------------------------------------------------------------------------


def test_seat_limit_blocks_at_cap() -> None:
    db = _db_with_active_user_count(5)
    config = {"tier": "evaluation", "max_seats": 5}
    with pytest.raises(SeatLimitExceeded) as exc_info:
        check_seat_limit(db, config)
    assert "5/5" in exc_info.value.detail
    assert "evaluation" in exc_info.value.detail


def test_seat_limit_blocks_above_cap() -> None:
    db = _db_with_active_user_count(7)
    config = {"tier": "evaluation", "max_seats": 5}
    with pytest.raises(SeatLimitExceeded):
        check_seat_limit(db, config)


def test_seat_limit_allows_below_cap() -> None:
    db = _db_with_active_user_count(3)
    check_seat_limit(db, {"tier": "evaluation", "max_seats": 5})  # no raise


def test_seat_limit_allows_at_zero_remaining() -> None:
    """Exactly one below the cap should still be allowed."""
    db = _db_with_active_user_count(4)
    check_seat_limit(db, {"tier": "evaluation", "max_seats": 5})  # no raise


def test_seat_limit_unlimited_when_zero() -> None:
    """max_seats == 0 means unlimited (Team / Enterprise)."""
    db = _db_with_active_user_count(999)
    check_seat_limit(db, {"tier": "team", "max_seats": 0})  # no raise


def test_seat_limit_unlimited_when_absent() -> None:
    """max_seats absent → treated as 0 (unlimited)."""
    db = _db_with_active_user_count(999)
    check_seat_limit(db, {})  # no raise


# ---------------------------------------------------------------------------
# check_query_quota
# ---------------------------------------------------------------------------


def test_monthly_query_limit_blocks_at_cap() -> None:
    db = _db_with_audit_count(5000)
    config = {"tier": "evaluation", "monthly_query_limit": 5000}
    with pytest.raises(QuotaExceeded) as exc_info:
        check_query_quota(db, config)
    assert "5000/5000" in exc_info.value.detail
    assert "evaluation" in exc_info.value.detail


def test_monthly_query_limit_blocks_above_cap() -> None:
    db = _db_with_audit_count(5001)
    config = {"tier": "evaluation", "monthly_query_limit": 5000}
    with pytest.raises(QuotaExceeded):
        check_query_quota(db, config)


def test_monthly_query_allows_below_cap() -> None:
    db = _db_with_audit_count(4999)
    check_query_quota(db, {"tier": "evaluation", "monthly_query_limit": 5000})  # no raise


def test_monthly_query_unlimited_when_zero() -> None:
    """monthly_query_limit == 0 means unlimited (Team / Enterprise)."""
    db = _db_with_audit_count(999999)
    check_query_quota(db, {"tier": "team", "monthly_query_limit": 0})  # no raise


def test_monthly_query_unlimited_when_absent() -> None:
    """monthly_query_limit absent → treated as 0 (unlimited)."""
    db = _db_with_audit_count(999999)
    check_query_quota(db, {})  # no raise


def test_monthly_query_only_counts_current_month() -> None:
    """The AuditLog filter must include a timestamp >= start-of-month filter.

    We verify this by asserting that the mock's .filter() is called (i.e.,
    the function doesn't short-circuit before the DB query). A full date
    filter test requires an integration DB; this unit test confirms the
    query path is followed.
    """
    db = _db_with_audit_count(0)
    check_query_quota(db, {"monthly_query_limit": 5000})
    # DB query was called (not short-circuited)
    db.query.return_value.filter.assert_called_once()


# ---------------------------------------------------------------------------
# check_tier_expiry
# ---------------------------------------------------------------------------


def test_expiry_blocks_expired_naive_datetime() -> None:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None).isoformat()
    with pytest.raises(TierExpired) as exc_info:
        check_tier_expiry({"tier_expires_at": yesterday})
    assert "expired" in exc_info.value.detail.lower()


def test_expiry_blocks_expired_utc_datetime() -> None:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    with pytest.raises(TierExpired):
        check_tier_expiry({"tier_expires_at": yesterday})


def test_expiry_passes_future_naive_datetime() -> None:
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).replace(tzinfo=None).isoformat()
    check_tier_expiry({"tier_expires_at": tomorrow})  # no raise


def test_expiry_passes_future_utc_datetime() -> None:
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    check_tier_expiry({"tier_expires_at": tomorrow})  # no raise


def test_expiry_passes_with_positive_tz_offset() -> None:
    """Datetime with an explicit '+02:00' offset — tests .astimezone(UTC) path."""
    # A future time in UTC+2 that is still in the future when converted to UTC
    from datetime import timezone  # noqa: PLC0415

    tz_plus2 = timezone(timedelta(hours=2))
    future_plus2 = (datetime.now(UTC) + timedelta(days=1)).astimezone(tz_plus2)
    check_tier_expiry({"tier_expires_at": future_plus2.isoformat()})  # no raise


def test_expiry_passes_with_negative_tz_offset() -> None:
    """Datetime with '-05:00' offset (US/Eastern)."""
    from datetime import timezone  # noqa: PLC0415

    tz_minus5 = timezone(timedelta(hours=-5))
    future_minus5 = (datetime.now(UTC) + timedelta(days=1)).astimezone(tz_minus5)
    check_tier_expiry({"tier_expires_at": future_minus5.isoformat()})  # no raise


def test_expiry_passes_when_key_absent() -> None:
    check_tier_expiry({})  # no raise


def test_expiry_passes_when_value_is_none() -> None:
    check_tier_expiry({"tier_expires_at": None})  # no raise


def test_expiry_passes_when_value_is_empty_string() -> None:
    check_tier_expiry({"tier_expires_at": ""})  # no raise


def test_expiry_not_enforced_on_team_tier_with_stale_expiry() -> None:
    """Upgrading evaluation→team without clearing tier_expires_at must not block access.

    Realistic upgrade path: admin sets tier=team but forgets to clear the old
    evaluation expiry date. The check must be a no-op for non-evaluation tiers.
    """
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    # Would block on evaluation tier, must pass on team tier
    check_tier_expiry({"tier": "team", "tier_expires_at": yesterday})  # no raise


def test_expiry_not_enforced_on_enterprise_tier_with_stale_expiry() -> None:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    check_tier_expiry({"tier": "enterprise", "tier_expires_at": yesterday})  # no raise


def test_expiry_still_enforced_on_evaluation_tier() -> None:
    """Evaluation tier expiry enforcement is unchanged after the tier-gating fix."""
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    with pytest.raises(TierExpired):
        check_tier_expiry({"tier": "evaluation", "tier_expires_at": yesterday})
