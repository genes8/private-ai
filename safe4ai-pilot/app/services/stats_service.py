"""Shared stats aggregation queries.

Used by both admin document routes and user account routes to avoid
duplicating the same five SQL expressions in two places.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk, IngestionStatus


def get_corpus_stats(db: Session, workspace_ids: list[str] | None = None) -> dict[str, int]:
    """Return aggregate document/chunk counts for the knowledge base.

    When ``workspace_ids`` is provided, counts are scoped to those workspaces.
    An empty list yields all-zero counts (the caller has no accessible workspace).
    The unscoped path keeps the original query shape for backward compatibility.
    """
    if workspace_ids is not None and not workspace_ids:
        return {"docCount": 0, "chunkCount": 0, "failedCount": 0, "inProgressCount": 0}

    scoped = workspace_ids is not None

    def _doc_count(*filters: Any) -> int:
        q = db.query(func.count(Document.id))
        if scoped:
            q = q.filter(Document.workspace_id.in_(workspace_ids))
        for f in filters:
            q = q.filter(f)
        return int(q.scalar() or 0)

    doc_count = _doc_count()
    chunk_q = db.query(func.count(DocumentChunk.id))
    if scoped:
        chunk_q = chunk_q.join(Document, Document.id == DocumentChunk.document_id).filter(
            Document.workspace_id.in_(workspace_ids)
        )
    chunk_count = chunk_q.scalar() or 0
    failed_count = _doc_count(Document.ingestion_status == IngestionStatus.failed)
    in_progress_count = _doc_count(
        Document.ingestion_status.in_([IngestionStatus.embedding, IngestionStatus.queued])
    )
    return {
        "docCount": int(doc_count),
        "chunkCount": int(chunk_count),
        "failedCount": int(failed_count),
        "inProgressCount": int(in_progress_count),
    }
