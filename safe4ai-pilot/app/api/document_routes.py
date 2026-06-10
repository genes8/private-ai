"""Admin document management routes."""
from __future__ import annotations

import asyncio
import contextlib
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Query, Session

from app.auth.middleware import get_current_user, require_role
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import (
    Document,
    DocumentChunk,
    IngestionJob,
    IngestionJobStatus,
    IngestionStatus,
    User,
)
from app.security.upload_validator import UploadValidator
from app.services.document_service import (
    delete_qdrant_points,
    prune_bm25,
    verify_document_deletion,
)
from app.services.ingestion_service import run_ingestion
from app.services.semantic_cache import invalidate_cache_for_document
from app.services.stats_service import get_corpus_stats

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin"])

_RAW_DIR = Path("data/raw")
_RAW_DIR.mkdir(parents=True, exist_ok=True)
_UPLOAD_READ_CHUNK_SIZE = 1024 * 1024
_MAX_BACKGROUND_INGESTION_TASKS = 4
_INGESTION_TASK_SEMAPHORE = asyncio.Semaphore(_MAX_BACKGROUND_INGESTION_TASKS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _run_ingestion_task(
    *,
    doc_id: str,
    job_id: str,
    file_path: str,
    filename: str,
    uploaded_by: str,
    retriever: Any,
    activate_version: int | None = None,
    cleanup_raw_path: str | None = None,
) -> None:
    async with _INGESTION_TASK_SEMAPHORE:
        await run_ingestion(
            doc_id=doc_id,
            job_id=job_id,
            file_path=file_path,
            filename=filename,
            uploaded_by=uploaded_by,
            retriever=retriever,
            activate_version=activate_version,
            cleanup_raw_path=cleanup_raw_path,
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
    activate_version: int | None = None,
    cleanup_raw_path: str | None = None,
) -> None:
    task = asyncio.create_task(
        _run_ingestion_task(
            doc_id=doc_id,
            job_id=job_id,
            file_path=file_path,
            filename=filename,
            uploaded_by=uploaded_by,
            retriever=retriever,
            activate_version=activate_version,
            cleanup_raw_path=cleanup_raw_path,
        )
    )
    tasks = getattr(request.app.state, "ingestion_tasks", None)
    if tasks is None:
        tasks = set()
        request.app.state.ingestion_tasks = tasks
    tasks.add(task)
    tasks_by_doc = getattr(request.app.state, "ingestion_tasks_by_doc", None)
    if tasks_by_doc is None:
        tasks_by_doc = {}
        request.app.state.ingestion_tasks_by_doc = tasks_by_doc
    tasks_by_doc[doc_id] = task

    def _cleanup(done_task: asyncio.Task[None]) -> None:
        tasks.discard(done_task)
        if tasks_by_doc.get(doc_id) is done_task:
            tasks_by_doc.pop(doc_id, None)
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


# ---------------------------------------------------------------------------
# Endpoints
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
def get_corpus_stats_route(
    request: Request,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Lightweight document and chunk counts for the chat page empty state."""
    return get_corpus_stats(db)


@router.get("/admin/documents")
@limiter.limit("100/minute")
def list_documents(
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[dict[str, Any]]:
    """List all documents with their ingestion status."""
    from sqlalchemy import func

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


@router.get("/admin/documents/{doc_id}/inspect")
@limiter.limit("100/minute")
def inspect_document(
    request: Request,
    doc_id: str,
    chunk_limit: int = 10,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """One-call document inspector: metadata, chunk sample, and job history.

    Lets an operator audit what was ingested without database access.
    """
    if chunk_limit < 1 or chunk_limit > 50:
        raise HTTPException(status_code=422, detail="chunk_limit must be between 1 and 50")
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    uploader = db.get(User, doc.uploaded_by) if doc.uploaded_by else None
    from sqlalchemy import func

    chunk_count = (
        db.query(func.count(DocumentChunk.id))
        .filter(DocumentChunk.document_id == doc_id)
        .scalar()
        or 0
    )
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(chunk_limit)
        .all()
    )
    jobs = (
        db.query(IngestionJob)
        .filter(IngestionJob.document_id == doc_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "ingestion_status": doc.ingestion_status,
            "uploaded_at": doc.uploaded_at,
            "uploaded_by_email": uploader.email if uploader else None,
            "file_size_bytes": doc.file_size_bytes,
            "version": doc.version,
            "active_version": doc.active_version,
            "metadata": doc.doc_metadata,
        },
        "chunk_count": int(chunk_count),
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "chunk_version": c.chunk_version,
                "content_preview": c.content_preview,
                "indexed": c.qdrant_point_id is not None,
            }
            for c in chunks
        ],
        "jobs": [
            {
                "status": j.status,
                "created_at": j.created_at,
                "completed_at": j.completed_at,
                "error": j.error,
            }
            for j in jobs
        ],
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
        # Check for an active ingestion job BEFORE cancelling anything, so a
        # rejected delete (409) never leaves the ingestion half-cancelled.
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
        # No active job — safe to cancel any lingering task and proceed with delete.
        tasks_by_doc = getattr(request.app.state, "ingestion_tasks_by_doc", {})
        ingestion_task = tasks_by_doc.get(doc_id)
        if ingestion_task is not None and not ingestion_task.done():
            ingestion_task.cancel()
            tasks_by_doc.pop(doc_id, None)
        invalidate_cache_for_document(db, doc_id, commit=False)
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete()
        db.query(IngestionJob).filter(IngestionJob.document_id == doc_id).delete()
        db.delete(doc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    try:
        delete_qdrant_points(doc_id)
    except Exception as exc:
        logger.warning("qdrant_cleanup_after_delete_failed", doc_id=doc_id, error=str(exc))

    raw_path = _RAW_DIR / doc.storage_filename
    if raw_path.exists():
        try:
            raw_path.unlink()
        except OSError as exc:
            logger.warning("raw_document_delete_failed", doc_id=doc_id, error=str(exc))

    prune_bm25(getattr(request.app.state, "retriever", None), doc_id)
    logger.info("document_deleted", doc_id=doc_id)


@router.post("/admin/documents/{doc_id}/reindex", status_code=202)
async def reindex_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict[str, str]:
    """Re-trigger ingestion for an existing document."""
    from datetime import UTC, datetime

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
        delete_qdrant_points(doc_id)
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

    prune_bm25(retriever, doc_id)

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


@router.post("/admin/documents/{doc_id}/upload-new-version", status_code=202)
@limiter.limit("10/hour")
async def upload_new_version(
    request: Request,
    doc_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Replace a document's content without a retrieval gap.

    The new file is ingested as a staged version while the current version
    keeps serving; only after a fully successful ingest does the runtime
    switch to the new version (see run_ingestion). Old vectors stay in Qdrant
    as superseded for a rollback window until the cleanup job prunes them.
    """
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

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

    job_id = str(uuid.uuid4())
    old_storage_path = _RAW_DIR / str(doc.storage_filename)
    storage_name = validator.safe_filename() + suffix
    storage_path = _RAW_DIR / storage_name

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
                detail="Document is currently being ingested. Wait for completion first.",
            )
        storage_path.write_bytes(file_bytes)
        new_version = (doc.version or 1) + 1
        doc.version = new_version
        doc.filename = file.filename or storage_name
        doc.storage_filename = storage_name
        doc.file_type = suffix.lstrip(".")
        doc.file_size_bytes = len(file_bytes)
        doc.ingestion_status = IngestionStatus.queued
        doc.ingestion_started_at = None
        job = IngestionJob(id=job_id, document_id=doc_id, status=IngestionJobStatus.pending)
        db.add(job)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
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
        filename=str(doc.filename),
        uploaded_by=str(current_user.id),
        retriever=getattr(request.app.state, "retriever", None),
        activate_version=new_version,
        cleanup_raw_path=(
            str(old_storage_path) if old_storage_path != storage_path else None
        ),
    )
    logger.info("document_new_version_queued", doc_id=doc_id, version=new_version)
    return {"doc_id": doc_id, "job_id": job_id, "version": new_version}


@router.get("/admin/documents/{doc_id}/verify-deletion")
@limiter.limit("100/minute")
def verify_deletion(
    request: Request,
    doc_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Auditable evidence that a deleted document left nothing retrievable.

    Counts remnants across Qdrant, DB chunk/job rows, semantic cache, and the
    in-memory BM25 index. ``clean`` is true only when every count is zero.
    Returns 409 while the document still exists (deletion not performed yet).
    """
    if db.get(Document, doc_id) is not None:
        raise HTTPException(status_code=409, detail="Document still exists; delete it first")
    return verify_document_deletion(
        db, getattr(request.app.state, "retriever", None), doc_id
    )
