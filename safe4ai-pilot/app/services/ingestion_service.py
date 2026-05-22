from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.orm import Session

from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.config import settings
from app.db import SessionLocal
from app.db.models import Document, IngestionJob, IngestionJobStatus, IngestionStatus
from app.services.rag_pipeline import RagPipeline
from app.services.runtime_config import build_embedding_provider, build_provider, build_vision_provider, load_runtime_config

logger = structlog.get_logger(__name__)

_QDRANT_COLLECTION = "documents"
_STUCK_THRESHOLD_MINUTES = 10
_PENDING_JOB_TIMEOUT_ERROR = "Background ingestion task did not start; retry upload or reindex."


async def run_ingestion(
    doc_id: str,
    job_id: str,
    file_path: str,
    filename: str,
    uploaded_by: str,
    retriever: HybridRetriever | None = None,
) -> None:
    """Background task: ingest a document and update job/document status.

    Opens its own DB session so the HTTP request session can be closed safely.
    """
    db: Session = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        doc = db.get(Document, doc_id)
        if job is None or doc is None:
            logger.warning("ingestion_records_missing", doc_id=doc_id, job_id=job_id)
            return

        runtime = load_runtime_config(db)
        job.status = IngestionJobStatus.embedding
        doc.ingestion_status = IngestionStatus.embedding
        doc.ingestion_started_at = datetime.now(UTC)
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
            document_version=doc.version or 1,
        )

        job.status = IngestionJobStatus.completed
        job.completed_at = datetime.now(UTC)
        doc = db.get(Document, doc_id)
        if doc is not None and doc.ingestion_status == IngestionStatus.embedding:
            doc.ingestion_status = IngestionStatus.indexed
        db.commit()
        logger.info("ingestion_completed", doc_id=doc_id)

    except Exception as exc:
        logger.error("ingestion_failed", doc_id=doc_id, error=str(exc))
        try:
            job = db.get(IngestionJob, job_id)
            doc = db.get(Document, doc_id)
            if job is not None:
                job.status = IngestionJobStatus.failed
                job.error = str(exc)[:2000]
                job.completed_at = datetime.now(UTC)
            if doc is not None:
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
        if doc is not None and doc.ingestion_status == IngestionStatus.queued:
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
