"""Audit log and semantic cache cleanup script.

Can be run standalone:
    python scripts/audit_cleanup.py

Or imported and scheduled:
    from scripts.audit_cleanup import run_cleanup, schedule_cleanup
"""

from __future__ import annotations

import hashlib
import hmac
import json
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


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _audit_log_record(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "session_id": row.session_id,
        "timestamp": (
            row.timestamp.isoformat() if isinstance(row.timestamp, datetime) else row.timestamp
        ),
        "action_type": row.action_type,
        "query_text": row.query_text,
        "response_metadata": row.response_metadata,
        "latency_ms": row.latency_ms,
        "model_used": row.model_used,
        "trace_id": row.trace_id,
    }


def _write_audit_archive(
    *,
    rows: list[AuditLog],
    archive_dir: str | Path,
    archive_secret: str,
    generated_at: datetime,
    audit_cutoff: datetime,
) -> dict[str, Any]:
    archive_path = Path(archive_dir)
    archive_path.mkdir(parents=True, exist_ok=True)

    stem = f"audit-{generated_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    jsonl_path = archive_path / f"{stem}.jsonl"
    manifest_path = archive_path / f"{stem}.manifest.json"

    previous_hash = "0" * 64
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = _audit_log_record(row)
            canonical = json.dumps(
                record,
                sort_keys=True,
                separators=(",", ":"),
                default=_json_default,
            )
            prior_hash = previous_hash
            row_hash = hashlib.sha256(f"{prior_hash}\n{canonical}".encode()).hexdigest()
            handle.write(
                json.dumps(
                    {**record, "_previous_hash": prior_hash, "_hash": row_hash},
                    sort_keys=True,
                    default=_json_default,
                )
                + "\n"
            )
            previous_hash = row_hash

    archive_sha256 = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    hmac_payload = f"{archive_sha256}:{previous_hash}:{len(rows)}".encode()
    manifest = {
        "format": "safe4ai.audit.archive.v1",
        "generated_at": generated_at.isoformat(),
        "cutoff": audit_cutoff.isoformat(),
        "row_count": len(rows),
        "archive_path": str(jsonl_path),
        "archive_sha256": archive_sha256,
        "final_hash": previous_hash,
        "hmac_sha256": hmac.new(
            archive_secret.encode(),
            hmac_payload,
            hashlib.sha256,
        ).hexdigest(),
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )

    for path in (jsonl_path, manifest_path):
        try:
            path.chmod(0o444)
        except OSError:
            logger.warning("audit_archive_chmod_failed", path=str(path))

    return {
        "archive_rows": len(rows),
        "archive_path": str(jsonl_path),
        "archive_manifest_path": str(manifest_path),
        "archive_sha256": archive_sha256,
        "archive_final_hash": previous_hash,
        "archive_hmac_sha256": manifest["hmac_sha256"],
    }


def run_cleanup(
    db: Session,
    retention_days: int,
    cache_retention_days: int,
    archive_dir: str | Path | None = None,
    archive_secret: str | None = None,
) -> dict[str, int]:
    """Delete stale audit logs and cache entries, then write a summary audit log.

    Args:
        db: Active SQLAlchemy session.
        retention_days: Delete audit_logs older than this many days.
        cache_retention_days: Delete semantic_cache entries older than this many days.
        archive_dir: Optional directory for audit JSONL + manifest export before deletion.
        archive_secret: HMAC key for archive manifests. Defaults to SECRET_KEY.

    Returns:
        {"audit_rows_deleted": n, "cache_rows_deleted": n, "audit_rows_archived": n}
    """
    now = datetime.now(UTC)
    audit_cutoff = now - timedelta(days=retention_days)
    cache_cutoff = now - timedelta(days=cache_retention_days)

    archive_metadata: dict[str, Any] = {"archive_rows": 0}
    if archive_dir is not None:
        expired_rows = (
            db.query(AuditLog)
            .filter(
                AuditLog.timestamp < audit_cutoff,
                AuditLog.action_type != "system_cleanup",
            )
            .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
            .all()
        )
        if expired_rows:
            archive_metadata = _write_audit_archive(
                rows=expired_rows,
                archive_dir=archive_dir,
                archive_secret=archive_secret or settings.secret_key,
                generated_at=now,
                audit_cutoff=audit_cutoff,
            )

    audit_result = db.execute(
        delete(AuditLog).where(
            AuditLog.timestamp < audit_cutoff,
            AuditLog.action_type != "system_cleanup",
        )
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
            **archive_metadata,
        },
    )
    db.add(summary_log)
    db.commit()

    logger.info(
        "audit_cleanup_complete",
        audit_rows_deleted=audit_deleted,
        cache_rows_deleted=cache_deleted,
    )
    return {
        "audit_rows_deleted": audit_deleted,
        "cache_rows_deleted": cache_deleted,
        "audit_rows_archived": int(archive_metadata["archive_rows"]),
    }


def schedule_cleanup(app: FastAPI) -> None:
    """Register a daily cleanup job with APScheduler at 02:00 UTC.

    Call this from the lifespan context manager in main.py after Phase 2B/2C merge.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    def _run_workspace_backfill_retry(**kwargs: Any) -> None:
        # Retry the Qdrant workspace_id backfill until it completes (e.g. after a
        # transient Qdrant outage at boot). No-op once the flag is set.
        from app.services.workspace_backfill import (
            backfill_qdrant_workspace_payload,
        )

        retriever = getattr(app.state, "retriever", None)
        try:
            backfill_qdrant_workspace_payload(retriever)
        except Exception as exc:  # noqa: BLE001
            logger.warning("workspace_backfill_retry_failed", error=str(exc))

    def _run_cleanup_wrapper(**kwargs: Any) -> None:
        db = SessionLocal()
        try:
            run_cleanup(
                db,
                retention_days=settings.audit_log_retention_days,
                cache_retention_days=settings.cache_retention_days,
                archive_dir=settings.audit_archive_dir or None,
                archive_secret=settings.secret_key,
            )
        finally:
            db.close()

    def _run_superseded_cleanup_wrapper(**kwargs: Any) -> None:
        from app.services.document_service import (
            cleanup_superseded_chunk_rows,
            delete_superseded_points,
        )

        try:
            delete_superseded_points(older_than_hours=24.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("superseded_points_cleanup_failed", error=str(exc))
        db = SessionLocal()
        try:
            cleanup_superseded_chunk_rows(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("superseded_chunks_cleanup_failed", error=str(exc))
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
    scheduler.add_job(
        _run_superseded_cleanup_wrapper,
        trigger="cron",
        hour=2,
        minute=30,
        id="superseded_version_cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_workspace_backfill_retry,
        trigger="interval",
        minutes=5,
        id="workspace_backfill_retry",
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
            archive_dir=settings.audit_archive_dir or None,
            archive_secret=settings.secret_key,
        )
        print(result)  # noqa: T201 — intentional CLI output
    finally:
        db.close()
