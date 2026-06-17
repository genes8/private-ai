"""One-time backfill of the Qdrant ``workspace_id`` payload for legacy vectors.

Retrieval is fail-closed on ``workspace_id`` (see ``HybridRetriever.retrieve``):
a vector with no ``workspace_id`` payload matches no workspace filter and is
therefore not retrievable. Vectors written before the workspace migration lack
that field, so on first boot after upgrade they would be invisible to search
until backfilled here.

This module assigns those legacy points to the default workspace, records a
completion flag in ``app_config``, and rebuilds the BM25 index so the sparse
path also carries ``workspace_id``. It is safe to run repeatedly; a Qdrant
outage leaves the flag unset so the caller (startup task / scheduler) retries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from qdrant_client import QdrantClient

from app.config import settings
from app.db import SessionLocal
from app.db.models import DEFAULT_WORKSPACE_ID
from app.services.app_config_store import load_app_config, upsert_app_config

if TYPE_CHECKING:
    from app.components.hybrid_retriever import HybridRetriever

logger = structlog.get_logger(__name__)

BACKFILL_FLAG = "qdrant_workspace_backfill_complete"
_QDRANT_COLLECTION = "documents"
_SCROLL_BATCH = 1000


def is_workspace_backfill_complete() -> bool:
    """True once every Qdrant point carries a ``workspace_id`` payload."""
    with SessionLocal() as db:
        return bool(load_app_config(db).get(BACKFILL_FLAG, False))


def _mark_complete() -> None:
    with SessionLocal() as db:
        upsert_app_config(db, {BACKFILL_FLAG: True})


def backfill_qdrant_workspace_payload(retriever: HybridRetriever | None = None) -> bool:
    """Assign legacy points to the default workspace; flip the flag on success.

    Returns True if the collection is fully tagged (flag set, BM25 rebuilt),
    False if Qdrant was unavailable or the pass did not complete — in which case
    the flag is left unset for a later retry.
    """
    if is_workspace_backfill_complete():
        return True

    try:
        client = QdrantClient(url=settings.qdrant_url)
        if not client.collection_exists(_QDRANT_COLLECTION):
            # Nothing to tag yet (fresh deployment); consider it complete.
            _mark_complete()
            return True

        tagged = 0
        offset: Any = None
        while True:
            points, next_offset = client.scroll(
                collection_name=_QDRANT_COLLECTION,
                limit=_SCROLL_BATCH,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            missing = [
                point.id
                for point in points
                if not (point.payload or {}).get("workspace_id")
            ]
            if missing:
                client.set_payload(
                    collection_name=_QDRANT_COLLECTION,
                    payload={"workspace_id": DEFAULT_WORKSPACE_ID},
                    points=missing,
                    wait=True,
                )
                tagged += len(missing)
            if next_offset is None:
                break
            offset = next_offset
    except Exception as exc:
        logger.warning("qdrant_workspace_backfill_failed", error=str(exc))
        return False

    _mark_complete()
    logger.info("qdrant_workspace_backfill_complete", tagged=tagged)

    # Rebuild BM25 so the sparse path's payloads also carry workspace_id.
    if retriever is not None:
        try:
            retriever.rebuild_from_qdrant()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("qdrant_workspace_backfill_bm25_rebuild_failed", error=str(exc))
    return True
