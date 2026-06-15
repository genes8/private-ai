"""Admin document management routes."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.auth.middleware import (
    get_active_workspace_id,
    get_current_user,
    require_role,
    require_workspace_admin,
)
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
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


def _authorize_doc(db: Session, user: User, doc_id: str) -> Document:
    """Load a document the user may administer, else 404.

    A document is administrable by an org-admin or by a workspace_admin of the
    document's workspace. Foreign documents return 404 (not 403) so they are
    indistinguishable from non-existent ones (avoids IDOR enumeration).
    """
    from app.services import workspace_service

    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not workspace_service.is_workspace_admin(db, user, str(doc.workspace_id)):
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def _run_ingestion_task(
    *,
    doc_id: str,
    job_id: str,
    file_path: str,
    filename: str,
    uploaded_by: str,
    retriever: Any,
    document_version_id: str | None = None,
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
            document_version_id=document_version_id,
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
    document_version_id: str | None = None,
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
            document_version_id=document_version_id,
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


def _document_active_version(db: Session, doc: Document) -> DocumentVersion | None:
    active_version_id = getattr(doc, "active_version_id", None)
    if not active_version_id:
        return None
    active = db.get(DocumentVersion, active_version_id)
    if isinstance(active, DocumentVersion):
        return active
    return None


def _document_filename(doc: Document, active_version: DocumentVersion | None) -> str:
    return active_version.filename if active_version is not None else str(doc.filename)


def _document_file_type(doc: Document, active_version: DocumentVersion | None) -> str:
    return active_version.file_type if active_version is not None else str(doc.file_type)


def _document_file_size(doc: Document, active_version: DocumentVersion | None) -> int | None:
    if active_version is not None:
        return active_version.file_size_bytes
    return doc.file_size_bytes


def _document_version_number(doc: Document, active_version: DocumentVersion | None) -> int:
    if active_version is not None:
        return int(active_version.version_number)
    return int(doc.active_version or doc.version or 1)


def _serialize_document_version(version: DocumentVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "document_id": version.document_id,
        "version_number": version.version_number,
        "filename": version.filename,
        "storage_filename": version.storage_filename,
        "file_type": version.file_type,
        "file_size_bytes": version.file_size_bytes,
        "checksum": version.checksum,
        "status": version.status,
        "created_by": version.created_by,
        "created_at": version.created_at,
        "ingestion_started_at": version.ingestion_started_at,
        "ingested_at": version.ingested_at,
        "activated_at": version.activated_at,
        "failed_at": version.failed_at,
        "failed_reason": version.failed_reason,
    }


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
    auth: tuple[User, str] = Depends(require_workspace_admin),
) -> dict[str, str]:
    """Upload a document into the active workspace and trigger ingestion."""
    current_user, workspace_id = auth
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
    version_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    doc = Document(
        id=doc_id,
        filename=file.filename or storage_name,
        storage_filename=storage_name,
        file_type=suffix.lstrip("."),
        ingestion_status=IngestionStatus.queued,
        uploaded_by=current_user.id,
        workspace_id=workspace_id,
        file_size_bytes=len(file_bytes),
        title=file.filename or storage_name,
    )
    version = DocumentVersion(
        id=version_id,
        document_id=doc_id,
        version_number=1,
        filename=file.filename or storage_name,
        storage_filename=storage_name,
        file_type=suffix.lstrip("."),
        file_size_bytes=len(file_bytes),
        checksum=hashlib.sha256(file_bytes).hexdigest(),
        status=DocumentVersionStatus.pending,
        created_by=current_user.id,
    )
    job = IngestionJob(
        id=job_id,
        document_id=doc_id,
        document_version_id=version_id,
        status=IngestionJobStatus.pending,
    )
    db.add(doc)
    db.add(version)
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
        document_version_id=version_id,
    )
    logger.info("document_upload_queued", doc_id=doc_id, filename=file.filename)
    return {"doc_id": doc_id, "job_id": job_id, "document_version_id": version_id}


@router.get("/admin/corpus-stats")
@limiter.limit("100/minute")
def get_corpus_stats_route(
    request: Request,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_active_workspace_id),
) -> dict[str, int]:
    """Document/chunk counts for the chat empty state, scoped to the active workspace.

    Member-facing (not admin-only): any member of the active workspace sees the
    counts for that workspace.
    """
    return get_corpus_stats(db, workspace_ids=[workspace_id])


@router.get("/admin/documents")
@limiter.limit("100/minute")
def list_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List documents in the workspaces the caller administers (org-admin: all)."""
    from app.services import workspace_service

    admin_workspace_ids = workspace_service.list_admin_workspace_ids_for_user(db, current_user)
    if not admin_workspace_ids:
        return []
    chunk_count_sq = (
        db.query(DocumentChunk.document_id, func.count(DocumentChunk.id).label("cnt"))
        .group_by(DocumentChunk.document_id)
        .subquery()
    )
    rows = (
        db.query(Document, func.coalesce(chunk_count_sq.c.cnt, 0).label("chunk_count"), User.email)
        .outerjoin(chunk_count_sq, Document.id == chunk_count_sq.c.document_id)
        .outerjoin(User, Document.uploaded_by == User.id)
        .filter(Document.workspace_id.in_(admin_workspace_ids))
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    documents = []
    for d, cnt, email in rows:
        active_version = _document_active_version(db, d)
        version_number = _document_version_number(d, active_version)
        documents.append(
            {
            "id": d.id,
            "filename": _document_filename(d, active_version),
            "file_type": _document_file_type(d, active_version),
            "ingestion_status": d.ingestion_status,
            "uploaded_at": d.uploaded_at,
            "uploaded_by_email": email,
            "version": version_number,
            "active_version": version_number,
            "active_version_id": getattr(d, "active_version_id", None),
            "chunk_count": cnt,
            "file_size_bytes": _document_file_size(d, active_version),
            }
        )
    return documents


@router.get("/admin/documents/{doc_id}/status")
@limiter.limit("100/minute")
def get_document_status(
    request: Request,
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Poll ingestion progress for a specific document."""
    doc = _authorize_doc(db, current_user, doc_id)
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
        "active_version_id": getattr(doc, "active_version_id", None),
    }


@router.get("/admin/documents/{doc_id}/inspect")
@limiter.limit("100/minute")
def inspect_document(
    request: Request,
    doc_id: str,
    chunk_limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """One-call document inspector: metadata, chunk sample, and job history.

    Lets an operator audit what was ingested without database access.
    """
    if chunk_limit < 1 or chunk_limit > 50:
        raise HTTPException(status_code=422, detail="chunk_limit must be between 1 and 50")
    doc = _authorize_doc(db, current_user, doc_id)

    active_version = _document_active_version(db, doc)
    uploader = db.get(User, doc.uploaded_by) if doc.uploaded_by else None

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
            "filename": _document_filename(doc, active_version),
            "file_type": _document_file_type(doc, active_version),
            "ingestion_status": doc.ingestion_status,
            "uploaded_at": doc.uploaded_at,
            "uploaded_by_email": uploader.email if uploader else None,
            "file_size_bytes": _document_file_size(doc, active_version),
            "version": _document_version_number(doc, active_version),
            "active_version": _document_version_number(doc, active_version),
            "active_version_id": getattr(doc, "active_version_id", None),
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


@router.get("/admin/documents/{doc_id}/versions")
@limiter.limit("100/minute")
def list_document_versions(
    request: Request,
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Read-only version history for a logical document."""
    doc = _authorize_doc(db, current_user, doc_id)

    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )
    return {
        "doc_id": doc_id,
        "active_version_id": getattr(doc, "active_version_id", None),
        "versions": [_serialize_document_version(version) for version in versions],
    }


@router.delete("/admin/documents/{doc_id}", status_code=204)
def delete_document(
    request: Request,
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a document from filesystem, vector store, DB, and semantic cache."""
    doc = _authorize_doc(db, current_user, doc_id)
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
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Re-trigger ingestion for an existing document.

    Recovery-only. This path deletes the document's vectors before re-ingesting,
    so it is NOT atomic — there is a window where the document is unsearchable, and
    a mid-reindex failure leaves no rollback. For routine document updates use the
    staged ``/admin/documents/{doc_id}/upload-new-version`` endpoint, which ingests
    the new version before flipping ``active_version`` and keeps a rollback window.
    Reach for ``reindex`` only when a document's index is stuck/corrupt and must be
    rebuilt from the stored raw file.
    """
    from datetime import UTC, datetime

    doc = _authorize_doc(db, current_user, doc_id)
    active_version = _document_active_version(db, doc)

    raw_path = _RAW_DIR / (
        active_version.storage_filename if active_version is not None else doc.storage_filename
    )
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
        job = IngestionJob(
            id=job_id,
            document_id=doc_id,
            document_version_id=active_version.id if active_version is not None else None,
            status=IngestionJobStatus.pending,
        )
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
        if active_version is not None:
            active_version.status = DocumentVersionStatus.pending
            active_version.ingestion_started_at = None
            active_version.ingested_at = None
            active_version.failed_at = None
            active_version.failed_reason = None
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
        filename=active_version.filename if active_version is not None else str(doc.filename),
        uploaded_by=str(current_user.id),
        retriever=retriever,
        document_version_id=active_version.id if active_version is not None else None,
    )
    return {"job_id": job_id}


@router.post("/admin/documents/{doc_id}/upload-new-version", status_code=202)
@limiter.limit("10/hour")
async def upload_new_version(
    request: Request,
    doc_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Replace a document's content without a retrieval gap.

    The new file is ingested as a staged version while the current version
    keeps serving; only after a fully successful ingest does the runtime
    switch to the new version (see run_ingestion). Old vectors stay in Qdrant
    as superseded for a rollback window until the cleanup job prunes them.
    """
    doc = _authorize_doc(db, current_user, doc_id)

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
    version_id = str(uuid.uuid4())
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
        latest_version = (
            db.query(func.max(DocumentVersion.version_number))
            .filter(DocumentVersion.document_id == doc_id)
            .scalar()
            or doc.version
            or doc.active_version
            or 1
        )
        new_version = int(latest_version) + 1
        doc.ingestion_status = IngestionStatus.queued
        doc.ingestion_started_at = None
        version = DocumentVersion(
            id=version_id,
            document_id=doc_id,
            version_number=new_version,
            filename=file.filename or storage_name,
            storage_filename=storage_name,
            file_type=suffix.lstrip("."),
            file_size_bytes=len(file_bytes),
            checksum=hashlib.sha256(file_bytes).hexdigest(),
            status=DocumentVersionStatus.pending,
            created_by=current_user.id,
        )
        job = IngestionJob(
            id=job_id,
            document_id=doc_id,
            document_version_id=version_id,
            status=IngestionJobStatus.pending,
        )
        db.add(version)
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
        filename=file.filename or storage_name,
        uploaded_by=str(current_user.id),
        retriever=getattr(request.app.state, "retriever", None),
        document_version_id=version_id,
        cleanup_raw_path=(
            str(old_storage_path) if old_storage_path != storage_path else None
        ),
    )
    logger.info("document_new_version_queued", doc_id=doc_id, version=new_version)
    return {
        "doc_id": doc_id,
        "job_id": job_id,
        "document_version_id": version_id,
        "version": new_version,
    }


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
