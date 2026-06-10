from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.config import settings
from app.db import SessionLocal
from app.db.models import (
    Document,
    DocumentVersion,
    DocumentVersionStatus,
    IngestionJob,
    IngestionJobStatus,
    IngestionStatus,
)
from app.services.document_service import activate_document_version
from app.services.rag_pipeline import RagPipeline
from app.services.runtime_config import (
    build_embedding_provider,
    build_provider,
    build_vision_provider,
    load_runtime_config,
)

logger = structlog.get_logger(__name__)

_QDRANT_COLLECTION = "documents"
_STUCK_THRESHOLD_MINUTES = 10
_PENDING_JOB_TIMEOUT_ERROR = "Background ingestion task did not start; retry upload or reindex."


def _string_id(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _sync_document_from_version(doc: Document, version: DocumentVersion) -> None:
    doc.active_version_id = version.id
    doc.version = version.version_number
    doc.active_version = version.version_number
    doc.filename = version.filename
    doc.storage_filename = version.storage_filename
    doc.file_type = version.file_type
    doc.file_size_bytes = version.file_size_bytes
    doc.ingestion_status = IngestionStatus.indexed


def _activate_document_version_with_commit_retry(
    db: Session,
    doc_id: str,
    version_id: str,
    retriever: HybridRetriever | None,
) -> None:
    """Flip Qdrant and commit the DB switch, retrying once after commit failure.

    Qdrant and Postgres cannot share a transaction. If the first DB commit
    fails after the Qdrant flip, rollback the session, reload canonical rows,
    and rerun the activation idempotently so the DB catches up to Qdrant.
    """
    doc = db.get(Document, doc_id)
    version = db.get(DocumentVersion, version_id)
    if doc is None or version is None:
        raise RuntimeError("Document version missing during activation")

    activate_document_version(db, doc, version, retriever=retriever)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.warning(
            "document_activation_commit_failed_retrying",
            doc_id=doc_id,
            document_version_id=version_id,
        )
        doc = db.get(Document, doc_id)
        version = db.get(DocumentVersion, version_id)
        if doc is None or version is None:
            raise RuntimeError("Document version missing during activation retry")
        activate_document_version(db, doc, version, retriever=retriever)
        db.commit()


async def run_ingestion(
    doc_id: str,
    job_id: str,
    file_path: str,
    filename: str,
    uploaded_by: str,
    retriever: HybridRetriever | None = None,
    document_version_id: str | None = None,
    cleanup_raw_path: str | None = None,
) -> None:
    """Background task: ingest a document and update job/document status.

    Opens its own DB session so the HTTP request session can be closed safely.

    With ``document_version_id`` set this ingests a concrete DocumentVersion.
    Replacement versions are staged (``is_active=False``) and auto-activated
    only after a successful ingest. A failed replacement version is marked
    failed while ``documents.active_version_id`` keeps serving the previous
    active version.
    ``cleanup_raw_path`` (the replaced version's raw file) is deleted only
    after a successful switch.
    """
    db: Session = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        doc = db.get(Document, doc_id)
        if job is None or doc is None:
            logger.warning("ingestion_records_missing", doc_id=doc_id, job_id=job_id)
            return
        target_version_id = _string_id(document_version_id) or _string_id(
            getattr(job, "document_version_id", None)
        )
        version = db.get(DocumentVersion, target_version_id) if target_version_id else None
        target_version_number = (
            version.version_number if version is not None else doc.version or 1
        )
        replacement_ingest = (
            version is not None
            and _string_id(getattr(doc, "active_version_id", None)) is not None
            and doc.active_version_id != version.id
        )

        runtime = load_runtime_config(db)
        job.status = IngestionJobStatus.embedding
        doc.ingestion_status = IngestionStatus.embedding
        doc.ingestion_started_at = datetime.now(UTC)
        if version is not None:
            version.status = DocumentVersionStatus.ingesting
            version.ingestion_started_at = doc.ingestion_started_at
        db.commit()

        chat_provider = build_provider(runtime)
        embedding_provider = build_embedding_provider(runtime)
        vision_provider = build_vision_provider(runtime)
        retriever = retriever or HybridRetriever(
            qdrant_url=settings.qdrant_url,
            collection=_QDRANT_COLLECTION,
            embedding_model=runtime.embedding_model,
            embedding_client=embedding_provider,
        )
        reranker = Reranker(model_name=runtime.reranker_model, enabled=runtime.reranker_enabled)
        pipeline = RagPipeline(
            retriever=retriever,
            reranker=reranker,
            ollama_url=settings.ollama_url,
            ollama_model=runtime.chat_model,
            embedding_model=runtime.embedding_model,
            qdrant_url=settings.qdrant_url,
            collection=_QDRANT_COLLECTION,
            db_session=db,
            chat_client=chat_provider,
            embedding_client=embedding_provider,
            vision_client=vision_provider,
            chunk_size=runtime.chunk_size,
            chunk_overlap=runtime.chunk_overlap,
            rerank_top_n=runtime.retrieval_k,
            min_rerank_score=runtime.score_floor,
            vision_model=runtime.vision_model,
        )

        await pipeline.ingest(
            file_path,
            doc_id,
            filename,
            uploaded_by,
            document_version=target_version_number,
            document_version_id=version.id if version is not None else None,
            activate=not replacement_ingest,
        )

        if version is not None:
            doc = db.get(Document, doc_id)
            if doc is None:
                raise RuntimeError("Document missing after ingest")
            if doc.ingestion_status == IngestionStatus.failed:
                raise RuntimeError("No indexable content extracted")
            version.status = DocumentVersionStatus.staged
            version.ingested_at = datetime.now(UTC)
            if replacement_ingest:
                db.commit()
                _activate_document_version_with_commit_retry(
                    db,
                    doc_id,
                    str(version.id),
                    retriever,
                )
                if retriever is not None:
                    await asyncio.to_thread(retriever.rebuild_from_qdrant)
                if cleanup_raw_path:
                    with contextlib.suppress(OSError):
                        Path(cleanup_raw_path).unlink(missing_ok=True)
            else:
                version.status = DocumentVersionStatus.active
                version.activated_at = datetime.now(UTC)
                _sync_document_from_version(doc, version)
                db.commit()
                if retriever is not None:
                    await asyncio.to_thread(retriever.rebuild_from_qdrant)
        job.status = IngestionJobStatus.completed
        job.completed_at = datetime.now(UTC)
        doc = db.get(Document, doc_id)
        if doc is not None and doc.ingestion_status == IngestionStatus.embedding:
            doc.ingestion_status = IngestionStatus.indexed
        db.commit()
        logger.info(
            "ingestion_completed",
            doc_id=doc_id,
            document_version_id=document_version_id,
        )

    except Exception as exc:
        logger.error("ingestion_failed", doc_id=doc_id, error=str(exc))
        try:
            job = db.get(IngestionJob, job_id)
            doc = db.get(Document, doc_id)
            target_version_id = _string_id(document_version_id) or _string_id(
                getattr(job, "document_version_id", None)
            )
            version = db.get(DocumentVersion, target_version_id) if target_version_id else None
            if job is not None:
                job.status = IngestionJobStatus.failed
                job.error = str(exc)[:2000]
                job.completed_at = datetime.now(UTC)
            if version is not None:
                version.status = DocumentVersionStatus.failed
                version.failed_at = datetime.now(UTC)
                version.failed_reason = str(exc)[:2000]
            if doc is not None:
                if (
                    version is not None
                    and _string_id(getattr(doc, "active_version_id", None)) is not None
                    and doc.active_version_id != version.id
                ):
                    # Replacement failed but the previous version still serves —
                    # keep the document usable instead of marking it failed.
                    doc.ingestion_status = IngestionStatus.indexed
                    with contextlib.suppress(OSError):
                        Path(file_path).unlink(missing_ok=True)
                else:
                    doc.ingestion_status = IngestionStatus.failed
            db.commit()
        except Exception as failure_exc:  # noqa: BLE001
            db.rollback()
            logger.exception(
                "ingestion_failure_state_update_failed",
                doc_id=doc_id,
                job_id=job_id,
                error=str(failure_exc),
            )
    finally:
        db.close()


def recover_stuck_jobs(db: Session) -> int:
    """On startup, reset ingestion jobs stuck in 'ingesting' > 10 min back to 'pending'.

    Returns the number of jobs recovered.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=_STUCK_THRESHOLD_MINUTES)
    stuck_embedding: list[IngestionJob] = (
        db.query(IngestionJob)
        .join(Document, IngestionJob.document_id == Document.id)
        .filter(
            IngestionJob.status == IngestionJobStatus.embedding,
            Document.ingestion_started_at < cutoff,
        )
        .all()
    )
    for job in stuck_embedding:
        job.status = IngestionJobStatus.pending
        doc = db.get(Document, job.document_id)
        if doc is not None:
            doc.ingestion_status = IngestionStatus.queued
            doc.ingestion_started_at = None
        version = (
            db.get(DocumentVersion, _string_id(getattr(job, "document_version_id", None)))
            if _string_id(getattr(job, "document_version_id", None))
            else None
        )
        if version is not None:
            version.status = DocumentVersionStatus.pending
            version.ingestion_started_at = None

    stuck_pending: list[IngestionJob] = (
        db.query(IngestionJob)
        .join(Document, IngestionJob.document_id == Document.id)
        .filter(
            IngestionJob.status == IngestionJobStatus.pending,
            IngestionJob.created_at < cutoff,
        )
        .all()
    )
    for job in stuck_pending:
        job.status = IngestionJobStatus.failed
        job.error = _PENDING_JOB_TIMEOUT_ERROR
        job.completed_at = datetime.now(UTC)
        doc = db.get(Document, job.document_id)
        version = (
            db.get(DocumentVersion, _string_id(getattr(job, "document_version_id", None)))
            if _string_id(getattr(job, "document_version_id", None))
            else None
        )
        if version is not None:
            version.status = DocumentVersionStatus.failed
            version.failed_at = datetime.now(UTC)
            version.failed_reason = _PENDING_JOB_TIMEOUT_ERROR
        if doc is not None and doc.ingestion_status == IngestionStatus.queued:
            if (
                version is not None
                and _string_id(getattr(doc, "active_version_id", None)) is not None
                and doc.active_version_id != version.id
            ):
                doc.ingestion_status = IngestionStatus.indexed
            else:
                doc.ingestion_status = IngestionStatus.failed

    recovered = len(stuck_embedding) + len(stuck_pending)
    if recovered:
        db.commit()
        logger.info(
            "recovered_stuck_jobs",
            count=recovered,
            reset_embedding=len(stuck_embedding),
            failed_pending=len(stuck_pending),
        )
    return recovered
