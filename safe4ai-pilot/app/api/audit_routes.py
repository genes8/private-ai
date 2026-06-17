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

from app.audit.kinds import AUDIT_KINDS, classify_action_type
from app.auth.middleware import get_current_user, require_role
from app.auth.router import limiter
from app.db import get_db
from app.db.models import AgentRun, AuditLog, SemanticCache, SemanticCacheHit, User

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])


def _resolve_audit_scope(db: Session, user: User) -> list[str] | None:
    """Workspace scope for admin audit/stats views (org-admin ⇒ None ⇒ unrestricted)."""
    from app.services import workspace_service

    try:
        return workspace_service.admin_workspace_scope(db, user)
    except workspace_service.WorkspaceAccessDenied:
        raise HTTPException(status_code=403, detail="Forbidden")


def _apply_audit_filters(
    q: Any,
    start: datetime | None,
    end: datetime | None,
    user_id: str | None,
    workspace_ids: list[str] | None = None,
) -> Any:
    if start:
        q = q.filter(AuditLog.timestamp >= start)
    if end:
        q = q.filter(AuditLog.timestamp <= end)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if workspace_ids is not None:
        q = q.filter(AuditLog.workspace_id.in_(workspace_ids))
    return q


def _action_types_for_kind(
    db: Session,
    kind: str,
    start: datetime | None,
    end: datetime | None,
    user_id: str | None,
    workspace_ids: list[str] | None = None,
) -> list[str]:
    """Resolve a UI kind to the raw action_type values present in range.

    Classification lives in Python (app.audit.kinds), so the filter is the
    distinct action types observed in the range that classify to *kind*.
    """
    distinct_q = _apply_audit_filters(
        db.query(AuditLog.action_type).distinct(), start, end, user_id, workspace_ids
    )
    return [t for (t,) in distinct_q.all() if classify_action_type(t) == kind]


@router.get("/admin/audit-logs")
@limiter.limit("100/minute")
def list_audit_logs(
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: str | None = None,
    kind: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    if limit < 1:
        raise HTTPException(status_code=422, detail="limit must be positive")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset cannot be negative")
    if kind is not None and kind not in AUDIT_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {', '.join(AUDIT_KINDS)}")
    scope = _resolve_audit_scope(db, current_user)
    q = (
        db.query(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.timestamp.desc())
    )
    q = _apply_audit_filters(q, start, end, user_id, scope)
    if kind is not None:
        matching_types = _action_types_for_kind(db, kind, start, end, user_id, scope)
        if not matching_types:
            return []
        q = q.filter(AuditLog.action_type.in_(matching_types))
    rows = q.offset(offset).limit(min(limit, 1000)).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, tuple):
            r, user_email = row
        else:
            r = row
            user_email = None
        result.append(
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_email": user_email,
                "session_id": r.session_id,
                "timestamp": r.timestamp,
                "action_type": r.action_type,
                "kind": classify_action_type(r.action_type),
                "query_text": r.query_text,
                "latency_ms": r.latency_ms,
                "model_used": r.model_used,
                "trace_id": r.trace_id,
            }
        )
    return result


@router.get("/admin/audit-logs/kind-counts")
@limiter.limit("100/minute")
def audit_kind_counts(
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Event counts per UI kind for the given range — drives the sidebar badges."""
    scope = _resolve_audit_scope(db, current_user)
    grouped_q = _apply_audit_filters(
        db.query(AuditLog.action_type, func.count(AuditLog.id)), start, end, user_id, scope
    ).group_by(AuditLog.action_type)
    counts: dict[str, int] = {k: 0 for k in AUDIT_KINDS}
    total = 0
    for action_type, n in grouped_q.all():
        counts[classify_action_type(action_type)] += int(n)
        total += int(n)
    return {"total": total, "kinds": counts}


@router.get("/admin/audit-logs/export.csv")
@limiter.limit("100/minute")
def export_audit_logs_csv(
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    scope = _resolve_audit_scope(db, current_user)
    q = _apply_audit_filters(
        db.query(AuditLog).order_by(AuditLog.timestamp.asc()), start, end, None, scope
    )
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


@router.get("/admin/workspace-backfill-status")
@limiter.limit("100/minute")
def workspace_backfill_status(
    request: Request,
    _admin: User = Depends(require_role("admin")),
) -> dict[str, bool]:
    """Operator readiness signal for the Qdrant workspace_id backfill.

    While ``complete`` is False, legacy documents are intentionally unsearchable
    (fail-closed retrieval); the admin UI surfaces a banner. Authenticated and
    admin-only so it never affects the public liveness probe.
    """
    from app.services.workspace_backfill import is_workspace_backfill_complete

    return {"complete": is_workspace_backfill_complete()}


@router.get("/admin/stats")
@limiter.limit("100/minute")
def get_stats(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate pilot stats: queries, latency, fallback rate, cache hit rate."""
    if days < 1 or days > 366:
        raise HTTPException(status_code=422, detail="days must be between 1 and 366")
    cutoff = datetime.now(UTC) - timedelta(days=days)
    scope = _resolve_audit_scope(db, current_user)

    def _audit(q: Any) -> Any:
        return q.filter(AuditLog.workspace_id.in_(scope)) if scope is not None else q

    def _agent(q: Any) -> Any:
        return q.filter(AgentRun.workspace_id.in_(scope)) if scope is not None else q

    total_queries = (
        _audit(db.query(func.count(AuditLog.id)).filter(AuditLog.timestamp >= cutoff)).scalar()
        or 0
    )
    avg_latency = _audit(
        db.query(func.avg(AuditLog.latency_ms)).filter(AuditLog.timestamp >= cutoff)
    ).scalar()
    total_cost = (
        _agent(db.query(func.sum(AgentRun.cost_usd)).filter(AgentRun.started_at >= cutoff)).scalar()
        or 0.0
    )
    # Cache hits are scoped via their parent SemanticCache.workspace_id.
    cache_hits_q = db.query(func.count(SemanticCacheHit.id)).filter(
        SemanticCacheHit.created_at >= cutoff
    )
    if scope is not None:
        cache_hits_q = cache_hits_q.join(
            SemanticCache, SemanticCache.id == SemanticCacheHit.cache_id
        ).filter(SemanticCache.workspace_id.in_(scope))
    cache_hits = cache_hits_q.scalar() or 0
    unique_users = (
        _audit(
            db.query(func.count(func.distinct(AuditLog.user_id))).filter(
                AuditLog.timestamp >= cutoff, AuditLog.user_id.isnot(None)
            )
        ).scalar()
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


@router.get("/admin/stats/timeseries")
@limiter.limit("100/minute")
def get_stats_timeseries(
    request: Request,
    days: int = 14,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Daily query/user/cost buckets for the last *days* days, zero-filled.

    Buckets are calendar days in UTC; the last bucket is today (partial).
    """
    if days < 1 or days > 90:
        raise HTTPException(status_code=422, detail="days must be between 1 and 90")
    scope = _resolve_audit_scope(db, current_user)
    today = datetime.now(UTC).date()
    first_day = today - timedelta(days=days - 1)
    cutoff = datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)

    audit_q = (
        db.query(
            func.date(AuditLog.timestamp),
            func.count(AuditLog.id),
            func.count(func.distinct(AuditLog.user_id)),
        )
        .filter(AuditLog.timestamp >= cutoff)
        .group_by(func.date(AuditLog.timestamp))
    )
    if scope is not None:
        audit_q = audit_q.filter(AuditLog.workspace_id.in_(scope))
    audit_rows = audit_q.all()
    cost_q = (
        db.query(func.date(AgentRun.started_at), func.sum(AgentRun.cost_usd))
        .filter(AgentRun.started_at >= cutoff)
        .group_by(func.date(AgentRun.started_at))
    )
    if scope is not None:
        cost_q = cost_q.filter(AgentRun.workspace_id.in_(scope))
    cost_rows = cost_q.all()

    def _day_key(value: Any) -> str:
        # func.date() yields date objects on Postgres and strings on SQLite.
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    queries_by_day = {_day_key(d): (int(n), int(u)) for d, n, u in audit_rows}
    cost_by_day = {_day_key(d): float(c or 0.0) for d, c in cost_rows}

    series: list[dict[str, Any]] = []
    for offset_days in range(days):
        day = (first_day + timedelta(days=offset_days)).isoformat()
        n_queries, n_users = queries_by_day.get(day, (0, 0))
        series.append(
            {
                "date": day,
                "queries": n_queries,
                "unique_users": n_users,
                "cost_usd": round(cost_by_day.get(day, 0.0), 4),
            }
        )
    return {"days": days, "series": series}
