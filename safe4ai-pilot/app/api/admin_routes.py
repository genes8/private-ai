from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

from app.auth.middleware import get_current_user, hash_password, require_role
from app.auth.router import limiter
from app.components.hybrid_retriever import HybridRetriever
from app.config import settings
from app.db import get_db
from app.db.models import (
    AgentRun,
    AuditLog,
    Document,
    DocumentChunk,
    HumanReviewQueue,
    IngestionJob,
    IngestionJobStatus,
    IngestionStatus,
    QueryFeedback,
    ReviewStatus,
    SemanticCacheHit,
    User,
    UserRole,
)
from app.db.models import (
    Session as DbSession,
)
from app.security.upload_validator import UploadValidator
from app.services.ingestion_service import run_ingestion
from app.services.semantic_cache import invalidate_cache_for_document

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_RAW_DIR = Path("data/raw")
_RAW_DIR.mkdir(parents=True, exist_ok=True)
_QDRANT_COLLECTION = "documents"
_UPLOAD_READ_CHUNK_SIZE = 1024 * 1024
_MAX_BACKGROUND_INGESTION_TASKS = 4
_INGESTION_TASK_SEMAPHORE = asyncio.Semaphore(_MAX_BACKGROUND_INGESTION_TASKS)
_DELETED_USER_ID = "00000000-0000-0000-0000-000000000001"
_DELETED_USER_EMAIL = "deleted@redacted.local"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateUserRequest(BaseModel):
    email: str
    password: str | None = None
    role: UserRole = UserRole.pilot_user

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.fullmatch(v):
            raise ValueError("Invalid email format")
        return v


def _validate_password_strength(password: str) -> None:
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


async def _run_ingestion_task(
    *,
    doc_id: str,
    job_id: str,
    file_path: str,
    filename: str,
    uploaded_by: str,
    retriever: HybridRetriever | None,
) -> None:
    async with _INGESTION_TASK_SEMAPHORE:
        await run_ingestion(
            doc_id=doc_id,
            job_id=job_id,
            file_path=file_path,
            filename=filename,
            uploaded_by=uploaded_by,
            retriever=retriever,
        )


def _schedule_ingestion_task(
    request: Request,
    *,
    doc_id: str,
    job_id: str,
    file_path: str,
    filename: str,
    uploaded_by: str,
    retriever: Any,
) -> None:
    task = asyncio.create_task(
        _run_ingestion_task(
            doc_id=doc_id,
            job_id=job_id,
            file_path=file_path,
            filename=filename,
            uploaded_by=uploaded_by,
            retriever=retriever,
        )
    )
    tasks = getattr(request.app.state, "ingestion_tasks", None)
    if tasks is None:
        tasks = set()
        request.app.state.ingestion_tasks = tasks
    tasks.add(task)

    def _cleanup(done_task: asyncio.Task[None]) -> None:
        tasks.discard(done_task)
        if done_task.cancelled():
            logger.warning("ingestion_task_cancelled", doc_id=doc_id, job_id=job_id)
            return
        exc = done_task.exception()
        if exc is not None:
            logger.exception(
                "ingestion_task_unhandled_error", doc_id=doc_id, job_id=job_id, error=str(exc)
            )

    task.add_done_callback(_cleanup)


def _lock_query(query: Query[Any]) -> Query[Any]:
    if query.__class__.__module__.startswith("unittest.mock"):
        return query
    with_for_update = getattr(query, "with_for_update", None)
    if callable(with_for_update):
        return with_for_update()
    return query


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------


@router.post("/admin/documents/upload", status_code=201)
@limiter.limit("10/hour")
async def upload_document(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict[str, str]:
    """Upload a document and trigger background ingestion."""
    file_bytes = await _read_upload_with_limit(file)
    validator = UploadValidator()
    result = validator.validate(
        filename=file.filename or "",
        content_type=file.content_type or "",
        file_bytes=file_bytes,
    )
    if not result.allowed:
        raise HTTPException(status_code=400, detail=result.reason)

    suffix = Path(file.filename or "").suffix.lower()
    if not suffix:
        raise HTTPException(
            status_code=400, detail="File must have an extension (e.g., .pdf, .docx, .txt)"
        )
    storage_name = validator.safe_filename() + suffix
    storage_path = _RAW_DIR / storage_name
    storage_path.write_bytes(file_bytes)

    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    doc = Document(
        id=doc_id,
        filename=file.filename or storage_name,
        storage_filename=storage_name,
        file_type=suffix.lstrip("."),
        ingestion_status=IngestionStatus.queued,
        uploaded_by=current_user.id,
        file_size_bytes=len(file_bytes),
    )
    job = IngestionJob(id=job_id, document_id=doc_id, status=IngestionJobStatus.pending)
    db.add(doc)
    db.add(job)
    try:
        db.commit()
    except Exception:
        db.rollback()
        with contextlib.suppress(OSError):
            if storage_path.exists():
                storage_path.unlink()
        raise

    _schedule_ingestion_task(
        request,
        doc_id=doc_id,
        job_id=job_id,
        file_path=str(storage_path),
        filename=file.filename or storage_name,
        uploaded_by=str(current_user.id),
        retriever=getattr(request.app.state, "retriever", None),
    )
    logger.info("document_upload_queued", doc_id=doc_id, filename=file.filename)
    return {"doc_id": doc_id, "job_id": job_id}


@router.get("/admin/corpus-stats")
@limiter.limit("100/minute")
def get_corpus_stats(
    request: Request,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Lightweight document and chunk counts for the chat page empty state."""
    doc_count = db.query(func.count(Document.id)).scalar() or 0
    chunk_count = db.query(func.count(DocumentChunk.id)).scalar() or 0
    failed_count = (
        db.query(func.count(Document.id))
        .filter(Document.ingestion_status == "failed")
        .scalar()
        or 0
    )
    in_progress_count = (
        db.query(func.count(Document.id))
        .filter(Document.ingestion_status.in_(["embedding", "queued"]))
        .scalar()
        or 0
    )
    return {
        "docCount": doc_count,
        "chunkCount": chunk_count,
        "failedCount": failed_count,
        "inProgressCount": in_progress_count,
    }


@router.get("/admin/documents")
@limiter.limit("100/minute")
def list_documents(
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    """List all documents with their ingestion status."""
    chunk_count_sq = (
        db.query(DocumentChunk.document_id, func.count(DocumentChunk.id).label("cnt"))
        .group_by(DocumentChunk.document_id)
        .subquery()
    )
    rows = (
        db.query(Document, func.coalesce(chunk_count_sq.c.cnt, 0).label("chunk_count"), User.email)
        .outerjoin(chunk_count_sq, Document.id == chunk_count_sq.c.document_id)
        .outerjoin(User, Document.uploaded_by == User.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "ingestion_status": d.ingestion_status,
            "uploaded_at": d.uploaded_at,
            "uploaded_by_email": email,
            "version": d.version,
            "active_version": d.active_version,
            "chunk_count": cnt,
            "file_size_bytes": d.file_size_bytes,
        }
        for d, cnt, email in rows
    ]


@router.get("/admin/documents/{doc_id}/status")
@limiter.limit("100/minute")
def get_document_status(
    request: Request,
    doc_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Poll ingestion progress for a specific document."""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    job = (
        db.query(IngestionJob)
        .filter(IngestionJob.document_id == doc_id)
        .order_by(IngestionJob.created_at.desc())
        .first()
    )
    return {
        "doc_id": doc_id,
        "ingestion_status": doc.ingestion_status,
        "job_status": job.status if job else None,
        "job_error": job.error if job else None,
        "ingestion_started_at": doc.ingestion_started_at,
    }


@router.delete("/admin/documents/{doc_id}", status_code=204)
def delete_document(
    request: Request,
    doc_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> None:
    """Delete a document from filesystem, vector store, DB, and semantic cache."""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        active_job = _lock_query(
            db.query(IngestionJob).filter(
                IngestionJob.document_id == doc_id,
                IngestionJob.status.in_(
                    [IngestionJobStatus.embedding, IngestionJobStatus.pending]
                ),
            )
        ).first()
        if active_job:
            raise HTTPException(
                status_code=409,
                detail="Document is currently being ingested. Wait for completion before deleting.",
            )
        invalidate_cache_for_document(db, doc_id, commit=False)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
        db.query(IngestionJob).filter(IngestionJob.document_id == doc_id).delete()
        db.delete(doc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    try:
        _delete_qdrant_points(doc_id)
    except Exception as exc:
        logger.warning("qdrant_cleanup_after_delete_failed", doc_id=doc_id, error=str(exc))

    raw_path = _RAW_DIR / doc.storage_filename
    if raw_path.exists():
        try:
            raw_path.unlink()
        except OSError as exc:
            logger.warning("raw_document_delete_failed", doc_id=doc_id, error=str(exc))

    retriever = getattr(request.app.state, "retriever", None)
    if retriever is not None and hasattr(retriever, "remove_from_bm25"):
        try:
            retriever.remove_from_bm25(doc_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("bm25_prune_failed", doc_id=doc_id, error=str(exc))
    logger.info("document_deleted", doc_id=doc_id)


@router.post("/admin/documents/{doc_id}/reindex", status_code=202)
async def reindex_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict[str, str]:
    """Re-trigger ingestion for an existing document."""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    raw_path = _RAW_DIR / doc.storage_filename
    if not raw_path.exists():
        raise HTTPException(status_code=409, detail="Raw file not found; upload again")

    retriever = getattr(request.app.state, "retriever", None)
    job_id = str(uuid.uuid4())
    try:
        active_job = _lock_query(
            db.query(IngestionJob).filter(
                IngestionJob.document_id == doc_id,
                IngestionJob.status.in_(
                    [IngestionJobStatus.embedding, IngestionJobStatus.pending]
                ),
            )
        ).first()
        if active_job:
            raise HTTPException(
                status_code=409,
                detail="Document is currently being ingested. Wait for completion before reindexing.",  # noqa: E501
            )
        job = IngestionJob(id=job_id, document_id=doc_id, status=IngestionJobStatus.pending)
        db.add(job)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    try:
        _delete_qdrant_points(doc_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("qdrant_delete_failed_aborting_reindex", doc_id=doc_id, error=str(exc))
        job.status = IngestionJobStatus.failed
        job.completed_at = datetime.now(UTC)
        job.error = "Failed to reset vector index before reindex"
        doc.ingestion_status = IngestionStatus.failed
        db.commit()
        raise HTTPException(
            status_code=502, detail="Failed to reset vector index for reindex"
        ) from exc
    if retriever is not None and hasattr(retriever, "remove_from_bm25"):
        try:
            retriever.remove_from_bm25(doc_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("bm25_prune_failed", doc_id=doc_id, error=str(exc))

    try:
        invalidate_cache_for_document(db, doc_id, commit=False)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
        doc.version = (doc.version or 1) + 1
        doc.active_version = doc.version
        doc.ingestion_status = IngestionStatus.queued
        doc.ingestion_started_at = None
        db.commit()
    except Exception:
        db.rollback()
        raise

    _schedule_ingestion_task(
        request,
        doc_id=doc_id,
        job_id=job_id,
        file_path=str(raw_path),
        filename=str(doc.filename),
        uploaded_by=str(current_user.id),
        retriever=retriever,
    )
    return {"job_id": job_id}


async def _read_upload_with_limit(file: UploadFile) -> bytes:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _delete_qdrant_points(doc_id: str) -> None:
    try:
        client = QdrantClient(url=settings.qdrant_url)
        client.delete(
            collection_name=_QDRANT_COLLECTION,
            points_selector=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="doc_id",
                        match=qmodels.MatchValue(value=doc_id),
                    )
                ]
            ),
        )
    except Exception as exc:
        logger.warning("qdrant_document_delete_failed", doc_id=doc_id, error=str(exc))
        raise


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get("/admin/users")
@limiter.limit("100/minute")
def list_users(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset cannot be negative")
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/admin/users", status_code=201)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    if body.password is None:
        raise HTTPException(status_code=422, detail="Password is required")
    _validate_password_strength(body.password)
    existing = db.query(User).filter(User.email == body.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    logger.info("user_created", user_id=str(user.id), email=body.email, invited=False)
    return {"id": str(user.id)}


@router.delete("/admin/users/{user_id}", status_code=204)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("admin")),
) -> None:
    if user_id == str(current_admin.id):
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot deactivate admin users")
    deleted_user = _ensure_deleted_user(db)
    db.query(Document).filter(Document.uploaded_by == user_id).update(
        {Document.uploaded_by: deleted_user.id},
        synchronize_session=False,
    )
    user_session_ids = [
        s.id for s in db.query(DbSession).filter(DbSession.user_id == user_id).all()
    ]
    if user_session_ids:
        db.query(AgentRun).filter(AgentRun.session_id.in_(user_session_ids)).delete(synchronize_session=False)
    db.query(DbSession).filter(DbSession.user_id == user_id).delete()
    db.query(QueryFeedback).filter(QueryFeedback.user_id == user_id).delete()
    db.query(HumanReviewQueue).filter(HumanReviewQueue.user_id == user_id).delete()
    db.query(AuditLog).filter(AuditLog.user_id == user_id).update(
        {AuditLog.user_id: None},
        synchronize_session=False,
    )
    user.is_active = False
    user.email = f"deactivated+{user.id}@redacted.local"
    user.password_hash = hash_password(secrets.token_urlsafe(24))
    user.failed_login_count = 0
    user.locked_until = None
    user.token_valid_after = datetime.now(UTC)
    db.commit()


def _ensure_deleted_user(db: Session) -> User:
    deleted_user = db.get(User, _DELETED_USER_ID)
    if deleted_user is not None:
        return deleted_user
    deleted_user = db.query(User).filter(User.email == _DELETED_USER_EMAIL).first()
    if deleted_user is not None:
        return deleted_user

    deleted_user = User(
        id=_DELETED_USER_ID,
        email=_DELETED_USER_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(24)),
        role=UserRole.pilot_user,
        is_active=False,
    )
    db.add(deleted_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(User).filter(User.email == _DELETED_USER_EMAIL).first()
        if existing is None:
            raise
        return existing
    return deleted_user


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Human review queue — no admin UI consumer.
# Intentionally kept as a complete backend feature ready for a future
# review-queue admin page. Callable directly via the API in the meantime.
# ---------------------------------------------------------------------------


@router.get("/admin/review-queue")
@limiter.limit("100/minute")
def list_review_queue(
    request: Request,
    status: ReviewStatus = ReviewStatus.pending,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    rows = (
        db.query(HumanReviewQueue)
        .filter(HumanReviewQueue.status == status)
        .order_by(HumanReviewQueue.id)
        .all()
    )
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "user_id": r.user_id,
            "query": r.query,
            "draft_answer": r.draft_answer,
            "risk_reason": r.risk_reason,
            "status": r.status,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at,
        }
        for r in rows
    ]


@router.post("/admin/review-queue/{item_id}/approve", status_code=200)
def approve_review_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    item = db.get(HumanReviewQueue, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != ReviewStatus.pending:
        raise HTTPException(status_code=409, detail="Item already reviewed")
    item.status = ReviewStatus.approved
    item.reviewed_by = str(current_admin.id)
    item.reviewed_at = datetime.now(UTC)
    db.commit()
    return {"status": "approved"}


@router.post("/admin/review-queue/{item_id}/reject", status_code=200)
def reject_review_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    item = db.get(HumanReviewQueue, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != ReviewStatus.pending:
        raise HTTPException(status_code=409, detail="Item already reviewed")
    item.status = ReviewStatus.rejected
    item.reviewed_by = str(current_admin.id)
    item.reviewed_at = datetime.now(UTC)
    db.commit()
    return {"status": "rejected"}


# ---------------------------------------------------------------------------
# Current user info (convenience endpoint)
# ---------------------------------------------------------------------------


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
