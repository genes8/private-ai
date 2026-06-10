"""Document lifecycle helpers shared by document routes."""
from __future__ import annotations

import time
from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy.orm import Session

from app.config import settings

logger = structlog.get_logger(__name__)

_QDRANT_COLLECTION = "documents"


def delete_qdrant_points(doc_id: str) -> None:
    """Delete all Qdrant vectors whose doc_id matches.  Raises on failure."""
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


def prune_bm25(retriever: Any, doc_id: str) -> None:
    """Remove doc chunks from the in-memory BM25 index. Best-effort."""
    if retriever is not None and hasattr(retriever, "remove_from_bm25"):
        try:
            retriever.remove_from_bm25(doc_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("bm25_prune_failed", doc_id=doc_id, error=str(exc))


def activate_document_version(doc_id: str, version: int) -> None:
    """Make *version* the only retrievable version of a document in Qdrant.

    Activation order matters: the new version is activated first, then the
    rest is superseded — a brief overlap of two active versions beats a
    window where retrieval sees none. Superseded points keep a
    ``superseded_at`` epoch so the cleanup job can enforce the rollback
    window. Raises on failure (callers must not switch active_version then).
    """
    client = QdrantClient(url=settings.qdrant_url)
    doc_match = qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc_id))
    version_match = qmodels.FieldCondition(
        key="doc_version", match=qmodels.MatchValue(value=version)
    )
    client.set_payload(
        collection_name=_QDRANT_COLLECTION,
        payload={"is_active": True},
        points=qmodels.Filter(must=[doc_match, version_match]),
    )
    client.set_payload(
        collection_name=_QDRANT_COLLECTION,
        payload={"is_active": False, "superseded_at": time.time()},
        points=qmodels.Filter(must=[doc_match], must_not=[version_match]),
    )
    logger.info("document_version_activated", doc_id=doc_id, version=version)


def delete_superseded_points(older_than_hours: float = 24.0) -> None:
    """Delete Qdrant points superseded longer than the rollback window ago."""
    cutoff = time.time() - older_than_hours * 3600
    client = QdrantClient(url=settings.qdrant_url)
    client.delete(
        collection_name=_QDRANT_COLLECTION,
        points_selector=qmodels.Filter(
            must=[
                qmodels.FieldCondition(key="is_active", match=qmodels.MatchValue(value=False)),
                qmodels.FieldCondition(key="superseded_at", range=qmodels.Range(lt=cutoff)),
            ]
        ),
    )
    logger.info("superseded_points_cleaned", older_than_hours=older_than_hours)


def cleanup_superseded_chunk_rows(db: Session) -> int:
    """Delete DocumentChunk rows whose version is no longer the active one.

    Companion to delete_superseded_points — DB chunk rows have no timestamp,
    so they are pruned whenever the cleanup job runs (the Qdrant rollback
    window is what guards quick rollback; chunk rows are only previews).
    Returns the number of rows deleted.
    """
    from app.db.models import Document, DocumentChunk

    deleted = 0
    docs = db.query(Document.id, Document.active_version).all()
    for doc_id, active_version in docs:
        deleted += (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == doc_id,
                DocumentChunk.chunk_version != (active_version or 1),
            )
            .delete()
        )
    if deleted:
        db.commit()
        logger.info("superseded_chunk_rows_cleaned", count=deleted)
    return deleted


def verify_document_deletion(db: Session, retriever: Any, doc_id: str) -> dict[str, Any]:
    """Count what remains of a document across every store.

    Used after delete to produce auditable evidence that nothing is
    retrievable: Qdrant points, DB chunk rows, ingestion jobs, semantic
    cache entries referencing the document, and in-memory BM25 entries.
    """
    import json as _json

    from sqlalchemy import func, text

    from app.db.models import DocumentChunk, IngestionJob

    client = QdrantClient(url=settings.qdrant_url)
    qdrant_points = client.count(
        collection_name=_QDRANT_COLLECTION,
        count_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc_id))]
        ),
        exact=True,
    ).count

    db_chunks = (
        db.query(func.count(DocumentChunk.id))
        .filter(DocumentChunk.document_id == doc_id)
        .scalar()
        or 0
    )
    db_jobs = (
        db.query(func.count(IngestionJob.id))
        .filter(IngestionJob.document_id == doc_id)
        .scalar()
        or 0
    )
    cache_entries = db.execute(
        text(
            "SELECT count(*) FROM semantic_cache "
            "WHERE source_document_ids::jsonb @> CAST(:doc_id_json AS jsonb)"
        ),
        {"doc_id_json": _json.dumps([doc_id])},
    ).scalar() or 0

    bm25_entries = 0
    payloads = getattr(retriever, "_bm25_payloads", None)
    if isinstance(payloads, dict):
        bm25_entries = sum(1 for p in payloads.values() if p.get("doc_id") == doc_id)

    counts = {
        "qdrant_points": int(qdrant_points),
        "db_chunks": int(db_chunks),
        "db_jobs": int(db_jobs),
        "semantic_cache_entries": int(cache_entries),
        "bm25_entries": bm25_entries,
    }
    return {"doc_id": doc_id, "clean": all(v == 0 for v in counts.values()), "counts": counts}
