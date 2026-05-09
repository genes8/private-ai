"""Audit log and semantic cache cleanup script.

Can be run standalone:
    python scripts/audit_cleanup.py

Or imported and scheduled:
    from scripts.audit_cleanup import run_cleanup, schedule_cleanup
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete
from sqlalchemy.orm import Session

# Allow running as a script from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import SessionLocal
from app.db.models import AuditLog, SemanticCache

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


def run_cleanup(
    db: Session,
    retention_days: int,
    cache_retention_days: int,
) -> dict[str, int]:
    """Delete stale audit logs and cache entries, then write a summary audit log.

    Args:
        db: Active SQLAlchemy session.
        retention_days: Delete audit_logs older than this many days.
        cache_retention_days: Delete semantic_cache entries older than this many days.

    Returns:
        {"audit_rows_deleted": n, "cache_rows_deleted": n}
    """
    now = datetime.now(UTC)
    audit_cutoff = now - timedelta(days=retention_days)
    cache_cutoff = now - timedelta(days=cache_retention_days)

    audit_result = db.execute(
        delete(AuditLog).where(AuditLog.timestamp < audit_cutoff)
    )
    audit_deleted: int = audit_result.rowcount

    cache_result = db.execute(
        delete(SemanticCache).where(SemanticCache.created_at < cache_cutoff)
    )
    cache_deleted: int = cache_result.rowcount

    summary_log = AuditLog(
        id=str(uuid.uuid4()),
        action_type="system_cleanup",
        timestamp=now,
        response_metadata={
            "audit_rows_deleted": audit_deleted,
            "cache_rows_deleted": cache_deleted,
            "retention_days": retention_days,
            "cache_retention_days": cache_retention_days,
        },
    )
    db.add(summary_log)
    db.commit()

    logger.info(
        "audit_cleanup_complete",
        audit_rows_deleted=audit_deleted,
        cache_rows_deleted=cache_deleted,
    )
    return {"audit_rows_deleted": audit_deleted, "cache_rows_deleted": cache_deleted}


def schedule_cleanup(app: FastAPI) -> None:  # noqa: ARG001
    """Register a daily cleanup job with APScheduler at 02:00 UTC.

    Call this from the lifespan context manager in main.py after Phase 2B/2C merge.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    def _run_cleanup_wrapper(**kwargs: Any) -> None:
        db = SessionLocal()
        try:
            run_cleanup(
                db,
                retention_days=settings.audit_log_retention_days,
                cache_retention_days=settings.cache_retention_days,
            )
        finally:
            db.close()

    scheduler.add_job(
        _run_cleanup_wrapper,
        trigger="cron",
        hour=2,
        minute=0,
        id="audit_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("audit_cleanup_scheduled", hour=2, minute=0)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        result = run_cleanup(
            db,
            retention_days=settings.audit_log_retention_days,
            cache_retention_days=settings.cache_retention_days,
        )
        print(result)  # noqa: T201 — intentional CLI output
    finally:
        db.close()
