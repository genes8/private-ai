from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import re
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Query
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user, hash_password, require_role
from app.auth.router import limiter
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
    Session as DbSession,
    SemanticCache,
    SemanticCacheHit,
    User,
    UserRole,
)
from app.security.upload_validator import UploadValidator
from app.services.ingestion_service import run_ingestion
from app.services.app_config_store import load_app_config, upsert_app_config
from app.services.runtime_config import build_runtime_components
from app.services.semantic_cache import invalidate_cache_for_document
from observability.cost_tracker import CostTracker

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
_SETTINGS_LIVE_TTL_SECONDS = 15.0
_settings_live_cache: dict[str, Any] = {
    "expires_at": 0.0,
    "today_cost": 0.0,
    "available_ollama_models": [],
}


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


def _validate_model_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be empty")
    if len(normalized) > 200:
        raise HTTPException(status_code=422, detail=f"{field_name} is too long")
    return normalized


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


def _get_settings_live_metadata(db: Session) -> tuple[float, list[str]]:
    now = time.monotonic()
    if now < float(_settings_live_cache["expires_at"]):
        return (
            float(_settings_live_cache["today_cost"]),
            list(_settings_live_cache["available_ollama_models"]),
        )

    today_cost = CostTracker(settings.cost_per_1k_tokens).get_stats(db, days=1)["total_cost_usd"]
    try:
        available_ollama_models = sorted(_fetch_ollama_model_names())
    except HTTPException:
        available_ollama_models = []
    _settings_live_cache.update(
        {
            "expires_at": now + _SETTINGS_LIVE_TTL_SECONDS,
            "today_cost": today_cost,
            "available_ollama_models": available_ollama_models,
        }
    )
    return float(today_cost), list(available_ollama_models)


def _serialize_settings(db: Session) -> dict[str, Any]:
    db_overrides = load_app_config(db)

    def _val(key: str, default: Any) -> Any:
        return db_overrides.get(key, default)

    today_cost, available_ollama_models = _get_settings_live_metadata(db)
    current_ollama_models = {
        str(_val("generation_model", settings.ollama_model)),
        str(_val("generation_fallback_model", settings.ollama_model)),
        str(_val("embedding_model", settings.embedding_model)),
        str(_val("vision_model", "qwen2.5vl:7b")),
    }
    provider_api_key_raw = _val("provider_api_key", "")
    return {
        "generationModel": _val("generation_model", settings.ollama_model),
        "generationFallback": _val("generation_fallback_model", settings.ollama_model),
        "embeddingModel": _val("embedding_model", settings.embedding_model),
        "visionModel": _val("vision_model", "qwen2.5vl:7b"),
        "provider": {
            "type": _val("provider_type", "ollama"),
            "baseUrl": _val("provider_base_url", settings.ollama_url),
            "apiKeyConfigured": bool(provider_api_key_raw),
            "chatModel": _val(
                "provider_chat_model", _val("generation_model", settings.ollama_model)
            ),
            "embeddingModel": _val(
                "provider_embedding_model", _val("embedding_model", settings.embedding_model)
            ),
            "visionModel": _val("provider_vision_model", "qwen2.5vl:7b"),
        },
        "sseDoneMode": _val("sse_done_mode", "strict"),
        "availableModels": {
            "ollama": sorted(set(available_ollama_models) | current_ollama_models),
            "reranker": [
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "bge-reranker-v2",
            ],
        },
        "reranker": {
            "enabled": _val("reranker_enabled", True),
            "model": _val("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        },
        "retrieval": {
            "k": _val("retrieval_k", 6),
            "scoreFloor": _val("score_floor", 0.45),
            "chunkSize": _val("chunk_size", 800),
            "chunkOverlap": _val("chunk_overlap", 150),
        },
        "sources": [
            {
                "id": "src-1",
                "kind": "watch",
                "label": "data/raw",
                "detail": "Local filesystem watch",
                "docCount": db.query(Document).count(),
                "syncedAt": "2h ago",
                "status": "ok",
            },
        ],
        "security": {
            "ssoOnly": _val("sso_only", False),
            "sessionHours": _val("session_hours", 24),
            "auditRetentionDays": _val("audit_retention_days", settings.audit_log_retention_days),
            "redactPII": _val("redact_pii", False),
        },
        "cost": {
            "dailyCeilingUsd": _val("daily_ceiling_usd", 50),
            "monthlyCeilingUsd": _val("monthly_ceiling_usd", 500),
            "todayUsd": today_cost,
        },
    }


def _fetch_ollama_model_names() -> set[str]:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Unable to verify model availability") from exc

    body = resp.json()
    models = body.get("models", [])
    names = {
        str(model.get("name", "")).strip()
        for model in models
        if isinstance(model, dict) and model.get("name")
    }
    return {name for name in names if name}


def _validate_ollama_model_exists(value: str, field_name: str, available_models: set[str]) -> str:
    normalized = _validate_model_identifier(value, field_name)
    if normalized not in available_models:
        raise HTTPException(status_code=422, detail=f"{field_name} is not available in Ollama")
    return normalized


def _validate_embedding_model_dimension(model: str) -> None:
    """Raise 409 if the new embedding model's known dimension differs from the collection's."""
    from app.services.runtime_config import expected_vector_size

    expected = expected_vector_size(model)
    if expected is None:
        return
    try:
        from qdrant_client import QdrantClient as _QC

        info = _QC(url=settings.qdrant_url).get_collection("documents")
        vectors_cfg = info.config.params.vectors
        actual: int = (
            next(iter(vectors_cfg.values())).size  # type: ignore[union-attr]
            if isinstance(vectors_cfg, dict)
            else vectors_cfg.size  # type: ignore[union-attr]
        )
        if actual != expected:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Embedding model '{model}' requires vector size {expected} but "
                    f"the Qdrant collection currently has size {actual}. "
                    "Drop and recreate the collection before switching embedding models."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        pass  # If Qdrant is unreachable, allow the update and let startup guard catch it


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
            logger.exception("ingestion_task_unhandled_error", doc_id=doc_id, job_id=job_id, error=str(exc))

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
        raise HTTPException(status_code=400, detail="File must have an extension (e.g., .pdf, .docx, .txt)")
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
        db.query(Document, func.coalesce(chunk_count_sq.c.cnt, 0).label("chunk_count"))
        .outerjoin(chunk_count_sq, Document.id == chunk_count_sq.c.document_id)
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
            "version": d.version,
            "active_version": d.active_version,
            "chunk_count": cnt,
            "file_size_bytes": d.file_size_bytes,
        }
        for d, cnt in rows
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
        with db.begin():
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
            detail="Document is currently being ingested. Wait for completion before reindexing.",
        )

    retriever = getattr(request.app.state, "retriever", None)
    job_id = str(uuid.uuid4())
    with db.begin():
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
                detail="Document is currently being ingested. Wait for completion before reindexing.",
            )
        job = IngestionJob(id=job_id, document_id=doc_id, status=IngestionJobStatus.pending)
        db.add(job)

    try:
        _delete_qdrant_points(doc_id)
        if retriever is not None and hasattr(retriever, "remove_from_bm25"):
            try:
                retriever.remove_from_bm25(doc_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("bm25_prune_failed", doc_id=doc_id, error=str(exc))
    except Exception as exc:
        failed_job = db.get(IngestionJob, job_id)
        if failed_job is not None:
            failed_job.status = IngestionJobStatus.failed
            failed_job.completed_at = datetime.now(UTC)
            failed_job.error = "Failed to reset search indexes before reindex"
        doc.ingestion_status = IngestionStatus.failed
        db.commit()
        raise HTTPException(status_code=502, detail="Failed to reset vector index for reindex") from exc

    with db.begin():
        invalidate_cache_for_document(db, doc_id, commit=False)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
        doc.version = (doc.version or 1) + 1
        doc.active_version = doc.version
        doc.ingestion_status = IngestionStatus.queued
        doc.ingestion_started_at = None

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
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    users = db.query(User).order_by(User.created_at.desc()).all()
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
# Settings
# ---------------------------------------------------------------------------


@router.get("/settings")
@limiter.limit("100/minute")
def get_settings(
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Return current application settings, mixing env vars with DB overrides."""
    return _serialize_settings(db)


class PatchSettingsRequest(BaseModel):
    generationModel: str | None = None
    generationFallback: str | None = None
    embeddingModel: str | None = None
    visionModel: str | None = None
    rerankerEnabled: bool | None = None
    rerankerModel: str | None = None
    retrievalK: int | None = None
    scoreFloor: float | None = None
    chunkSize: int | None = None
    chunkOverlap: int | None = None
    ssoOnly: bool | None = None
    sessionHours: int | None = None
    auditRetentionDays: int | None = None
    redactPII: bool | None = None
    dailyCeilingUsd: float | None = None
    monthlyCeilingUsd: float | None = None
    # Inference provider fields
    providerType: str | None = None
    providerBaseUrl: str | None = None
    providerApiKey: str | None = None
    providerChatModel: str | None = None
    providerEmbeddingModel: str | None = None
    providerVisionModel: str | None = None
    sseDoneMode: str | None = None


@router.patch("/settings", status_code=200)
def patch_settings(
    request: Request,
    body: PatchSettingsRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Update mutable application settings stored in the DB."""
    current_config = load_app_config(db)
    updates: dict[str, Any] = {}
    requested_ollama_models = any(
        value is not None
        for value in (
            body.generationModel,
            body.generationFallback,
            body.embeddingModel,
            body.visionModel,
        )
    )
    available_ollama_models = _fetch_ollama_model_names() if requested_ollama_models else set()
    if body.generationModel is not None:
        updates["generation_model"] = _validate_ollama_model_exists(
            body.generationModel, "generationModel", available_ollama_models
        )
    if body.generationFallback is not None:
        updates["generation_fallback_model"] = _validate_ollama_model_exists(
            body.generationFallback, "generationFallback", available_ollama_models
        )
    if body.embeddingModel is not None:
        updates["embedding_model"] = _validate_ollama_model_exists(
            body.embeddingModel, "embeddingModel", available_ollama_models
        )
        _validate_embedding_model_dimension(body.embeddingModel)
    if body.visionModel is not None:
        updates["vision_model"] = _validate_ollama_model_exists(
            body.visionModel, "visionModel", available_ollama_models
        )
    if body.rerankerEnabled is not None:
        updates["reranker_enabled"] = body.rerankerEnabled
    if body.rerankerModel is not None:
        updates["reranker_model"] = _validate_model_identifier(
            body.rerankerModel, "rerankerModel"
        )
    if body.retrievalK is not None:
        if body.retrievalK < 1 or body.retrievalK > 32:
            raise HTTPException(status_code=422, detail="retrievalK must be between 1 and 32")
        updates["retrieval_k"] = body.retrievalK
    if body.scoreFloor is not None:
        if body.scoreFloor < 0 or body.scoreFloor > 1:
            raise HTTPException(status_code=422, detail="scoreFloor must be between 0 and 1")
        updates["score_floor"] = body.scoreFloor
    if body.chunkSize is not None:
        if body.chunkSize < 128 or body.chunkSize > 2048:
            raise HTTPException(status_code=422, detail="chunkSize must be between 128 and 2048")
        current_overlap = int(current_config.get("chunk_overlap", 150))
        if body.chunkOverlap is None and current_overlap >= body.chunkSize:
            raise HTTPException(status_code=422, detail="chunkSize must be larger than chunkOverlap")
        updates["chunk_size"] = body.chunkSize
    if body.chunkOverlap is not None:
        if body.chunkOverlap < 0 or body.chunkOverlap > 512:
            raise HTTPException(status_code=422, detail="chunkOverlap must be between 0 and 512")
        current_chunk_size = int(current_config.get("chunk_size", 800))
        effective_chunk_size = body.chunkSize if body.chunkSize is not None else current_chunk_size
        if body.chunkOverlap >= effective_chunk_size:
            raise HTTPException(status_code=422, detail="chunkOverlap must be smaller than chunkSize")
        updates["chunk_overlap"] = body.chunkOverlap
    if body.ssoOnly is not None:
        updates["sso_only"] = body.ssoOnly
    if body.sessionHours is not None:
        if body.sessionHours < 1 or body.sessionHours > 720:
            raise HTTPException(status_code=422, detail="sessionHours must be between 1 and 720")
        updates["session_hours"] = body.sessionHours
    if body.auditRetentionDays is not None:
        if body.auditRetentionDays < 30 or body.auditRetentionDays > 3650:
            raise HTTPException(status_code=422, detail="auditRetentionDays must be between 30 and 3650")
        updates["audit_retention_days"] = body.auditRetentionDays
    if body.redactPII is not None:
        updates["redact_pii"] = body.redactPII
    if body.dailyCeilingUsd is not None:
        if body.dailyCeilingUsd < 1 or body.dailyCeilingUsd > 10000:
            raise HTTPException(status_code=422, detail="dailyCeilingUsd must be between 1 and 10000")
        updates["daily_ceiling_usd"] = body.dailyCeilingUsd
    if body.monthlyCeilingUsd is not None:
        if body.monthlyCeilingUsd < 30 or body.monthlyCeilingUsd > 300000:
            raise HTTPException(status_code=422, detail="monthlyCeilingUsd must be between 30 and 300000")
        updates["monthly_ceiling_usd"] = body.monthlyCeilingUsd

    # Inference provider fields
    if body.providerType is not None:
        if body.providerType not in {"ollama", "openai_compatible"}:
            raise HTTPException(
                status_code=422, detail="providerType must be ollama or openai_compatible"
            )
        updates["provider_type"] = body.providerType
    if body.providerBaseUrl is not None:
        updates["provider_base_url"] = body.providerBaseUrl.rstrip("/")
    if body.providerApiKey is not None:
        updates["provider_api_key"] = body.providerApiKey
    if body.providerChatModel is not None:
        updates["provider_chat_model"] = _validate_model_identifier(
            body.providerChatModel, "providerChatModel"
        )
    if body.providerEmbeddingModel is not None:
        updates["provider_embedding_model"] = _validate_model_identifier(
            body.providerEmbeddingModel, "providerEmbeddingModel"
        )
        _validate_embedding_model_dimension(body.providerEmbeddingModel)
    if body.providerVisionModel is not None:
        updates["provider_vision_model"] = _validate_model_identifier(
            body.providerVisionModel, "providerVisionModel"
        )
    if body.sseDoneMode is not None:
        if body.sseDoneMode not in {"strict", "async"}:
            raise HTTPException(status_code=422, detail="sseDoneMode must be strict or async")
        updates["sse_done_mode"] = body.sseDoneMode

    # Require API key when switching to openai_compatible
    effective_provider = body.providerType or current_config.get("provider_type", "ollama")
    effective_key = body.providerApiKey or current_config.get("provider_api_key")
    if effective_provider == "openai_compatible" and not effective_key:
        raise HTTPException(
            status_code=422, detail="providerApiKey is required for openai_compatible"
        )

    upsert_app_config(db, updates, commit=False)
    db.commit()
    try:
        _runtime, retriever, reranker, graph = build_runtime_components(db)
        request.app.state.retriever = retriever
        request.app.state.reranker = reranker
        request.app.state.graph = graph
    except Exception as exc:  # noqa: BLE001
        logger.warning("runtime_refresh_failed", error=str(exc))
    logger.info("settings_updated", keys=list(updates.keys()))
    return _serialize_settings(db)


@router.post("/settings/provider/test", status_code=200)
def test_provider_connection(
    request: Request,
    body: PatchSettingsRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    """Validate provider credentials with a lightweight connectivity check."""
    from app.services.provider_clients import OpenAICompatibleProvider

    provider_type = body.providerType or str(load_app_config(db).get("provider_type", "ollama"))
    base_url = body.providerBaseUrl or str(
        load_app_config(db).get("provider_base_url", settings.ollama_url)
    )
    api_key = body.providerApiKey or load_app_config(db).get("provider_api_key", "")

    if provider_type == "openai_compatible":
        if not api_key:
            raise HTTPException(status_code=422, detail="providerApiKey is required for openai_compatible")
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code >= 500:
                    raise HTTPException(status_code=503, detail="Provider returned server error")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Connection failed: {exc}") from exc
    else:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{base_url.rstrip('/')}/api/tags")
                if resp.status_code >= 400:
                    raise HTTPException(status_code=503, detail="Ollama not reachable")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Ollama connection failed: {exc}") from exc

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Human review queue
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
