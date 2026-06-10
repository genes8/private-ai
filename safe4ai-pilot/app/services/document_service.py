"""Document lifecycle helpers shared by document routes."""
from __future__ import annotations

import time
from datetime import UTC, datetime
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


def flip_qdrant_active_version(
    doc_id: str,
    version: int,
    *,
    document_version_id: str | None = None,
) -> None:
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
    version_conditions = [doc_match, version_match]
    supersede_exclusions = [version_match]
    if document_version_id is not None:
        version_id_match = qmodels.FieldCondition(
            key="document_version_id", match=qmodels.MatchValue(value=document_version_id)
        )
        version_conditions.append(version_id_match)
        supersede_exclusions = [version_id_match]
    client.set_payload(
        collection_name=_QDRANT_COLLECTION,
        payload={"is_active": True},
        points=qmodels.Filter(must=version_conditions),
    )
    client.set_payload(
        collection_name=_QDRANT_COLLECTION,
        payload={"is_active": False, "superseded_at": time.time()},
        points=qmodels.Filter(must=[doc_match], must_not=supersede_exclusions),
    )
    logger.info("document_version_activated", doc_id=doc_id, version=version)


def activate_document_version(
    db: Session,
    doc: Any,
    new_version: Any,
    *,
    retriever: Any | None = None,
) -> None:
    """Activate a DocumentVersion in the DB lifecycle and Qdrant.

    Qdrant-only callers must use ``flip_qdrant_active_version`` directly. This
    function owns the production lifecycle transition for a concrete DB version.
    """
    from app.db.models import DocumentVersion, DocumentVersionStatus, IngestionStatus

    if new_version is None:
        raise ValueError("new_version is required for activation")

    new_version.status = DocumentVersionStatus.activating
    db.flush()
    flip_qdrant_active_version(
        str(doc.id),
        int(new_version.version_number),
        document_version_id=str(new_version.id),
    )

    old_active_id = getattr(doc, "active_version_id", None)
    if old_active_id and old_active_id != new_version.id:
        old_version = db.get(DocumentVersion, old_active_id)
        if old_version is not None:
            old_version.status = DocumentVersionStatus.superseded

    now = datetime.now(UTC)
    doc.active_version_id = new_version.id
    # Compatibility mirrors for existing API clients. Read paths should prefer
    # DocumentVersion, but these fields stay coherent during the transition.
    doc.version = new_version.version_number
    doc.active_version = new_version.version_number
    doc.filename = new_version.filename
    doc.storage_filename = new_version.storage_filename
    doc.file_type = new_version.file_type
    doc.file_size_bytes = new_version.file_size_bytes
    doc.ingestion_status = IngestionStatus.indexed
    new_version.status = DocumentVersionStatus.active
    new_version.activated_at = now
    if retriever is not None and hasattr(retriever, "rebuild_from_qdrant"):
        logger.debug("document_version_activation_rebuild_deferred", doc_id=doc.id)


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
    docs = db.query(Document.id, Document.active_version, Document.active_version_id).all()
    for doc_id, active_version, active_version_id in docs:
        filters = [DocumentChunk.document_id == doc_id]
        if active_version_id is not None:
            filters.append(DocumentChunk.document_version_id != active_version_id)
        else:
            filters.append(DocumentChunk.chunk_version != (active_version or 1))
        deleted += (
            db.query(DocumentChunk)
            .filter(*filters)
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

    from app.db.models import DocumentChunk, DocumentVersion, IngestionJob

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
    db_versions = (
        db.query(func.count(DocumentVersion.id))
        .filter(DocumentVersion.document_id == doc_id)
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
        "db_versions": int(db_versions),
        "db_jobs": int(db_jobs),
        "semantic_cache_entries": int(cache_entries),
        "bm25_entries": bm25_entries,
    }
    return {"doc_id": doc_id, "clean": all(v == 0 for v in counts.values()), "counts": counts}
