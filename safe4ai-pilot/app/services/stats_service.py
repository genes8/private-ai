"""Shared stats aggregation queries.

Used by both admin document routes and user account routes to avoid
duplicating the same five SQL expressions in two places.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk, IngestionStatus


def get_corpus_stats(db: Session) -> dict[str, int]:
    """Return aggregate document/chunk counts for the knowledge base."""
    doc_count = db.query(func.count(Document.id)).scalar() or 0
    chunk_count = db.query(func.count(DocumentChunk.id)).scalar() or 0
    failed_count = (
        db.query(func.count(Document.id))
        .filter(Document.ingestion_status == IngestionStatus.failed)
        .scalar()
        or 0
    )
    in_progress_count = (
        db.query(func.count(Document.id))
        .filter(
            Document.ingestion_status.in_([IngestionStatus.embedding, IngestionStatus.queued])
        )
        .scalar()
        or 0
    )
    return {
        "docCount": int(doc_count),
        "chunkCount": int(chunk_count),
        "failedCount": int(failed_count),
        "inProgressCount": int(in_progress_count),
    }
