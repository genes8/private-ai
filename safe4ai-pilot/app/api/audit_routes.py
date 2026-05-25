"""Admin audit log and stats routes."""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.middleware import require_role
from app.auth.router import limiter
from app.db import get_db
from app.db.models import AgentRun, AuditLog, SemanticCacheHit, User

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])


@router.get("/admin/audit-logs")
@limiter.limit("100/minute")
def list_audit_logs(
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    if limit < 1:
        raise HTTPException(status_code=422, detail="limit must be positive")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset cannot be negative")
    q = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if start:
        q = q.filter(AuditLog.timestamp >= start)
    if end:
        q = q.filter(AuditLog.timestamp <= end)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    rows = q.offset(offset).limit(min(limit, 1000)).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "session_id": r.session_id,
            "timestamp": r.timestamp,
            "action_type": r.action_type,
            "query_text": r.query_text,
            "latency_ms": r.latency_ms,
            "model_used": r.model_used,
            "trace_id": r.trace_id,
        }
        for r in rows
    ]


@router.get("/admin/audit-logs/export.csv")
@limiter.limit("100/minute")
def export_audit_logs_csv(
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> StreamingResponse:
    q = db.query(AuditLog).order_by(AuditLog.timestamp.asc())
    if start:
        q = q.filter(AuditLog.timestamp >= start)
    if end:
        q = q.filter(AuditLog.timestamp <= end)
    row_stream = q.limit(50_000).yield_per(500)
    fieldnames = [
        "id",
        "user_id",
        "session_id",
        "timestamp",
        "action_type",
        "query_text",
        "latency_ms",
        "model_used",
        "trace_id",
    ]

    def _iter_csv() -> Any:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        for r in row_stream:
            writer.writerow(
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "session_id": r.session_id,
                    "timestamp": r.timestamp,
                    "action_type": r.action_type,
                    "query_text": r.query_text,
                    "latency_ms": r.latency_ms,
                    "model_used": r.model_used,
                    "trace_id": r.trace_id,
                }
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    filename = f"audit_logs_{datetime.now(UTC).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/stats")
@limiter.limit("100/minute")
def get_stats(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Aggregate pilot stats: queries, latency, fallback rate, cache hit rate."""
    if days < 1 or days > 366:
        raise HTTPException(status_code=422, detail="days must be between 1 and 366")
    cutoff = datetime.now(UTC) - timedelta(days=days)

    total_queries = (
        db.query(func.count(AuditLog.id)).filter(AuditLog.timestamp >= cutoff).scalar() or 0
    )
    avg_latency = (
        db.query(func.avg(AuditLog.latency_ms)).filter(AuditLog.timestamp >= cutoff).scalar()
    )
    total_cost = (
        db.query(func.sum(AgentRun.cost_usd)).filter(AgentRun.started_at >= cutoff).scalar() or 0.0
    )
    cache_hits = (
        db.query(func.count(SemanticCacheHit.id))
        .filter(SemanticCacheHit.created_at >= cutoff)
        .scalar()
        or 0
    )
    unique_users = (
        db.query(func.count(func.distinct(AuditLog.user_id)))
        .filter(AuditLog.timestamp >= cutoff, AuditLog.user_id.isnot(None))
        .scalar()
        or 0
    )

    return {
        "days": days,
        "total_queries": total_queries,
        "avg_latency_ms": round(float(avg_latency), 1) if avg_latency else None,
        "total_cost_usd": round(float(total_cost), 4),
        "cache_total_hits": int(cache_hits),
        "unique_users": int(unique_users),
        "generated_at": datetime.now(UTC),
    }
