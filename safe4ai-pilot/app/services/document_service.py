"""Document lifecycle helpers shared by document routes."""
from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels

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
