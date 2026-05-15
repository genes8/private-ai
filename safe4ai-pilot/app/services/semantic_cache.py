from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.db.models import SemanticCache as SemanticCacheModel
from app.db.models import SemanticCacheHit
from app.models import Citation
from app.services.provider_clients import EmbeddingClient


class SemanticCache:
    def __init__(
        self,
        db: Session,
        embedding_client: EmbeddingClient,
        threshold: float,
    ) -> None:
        self._db = db
        self._client = embedding_client
        self._threshold = threshold

    async def lookup(self, query: str) -> dict[str, Any] | None:
        embedding = await self._client.embed_query(query)
        distance = SemanticCacheModel.query_embedding.cosine_distance(embedding)
        stmt = (
            select(
                SemanticCacheModel.id,
                SemanticCacheModel.response_json,
                SemanticCacheModel.citations_json,
            )
            .where((1 - distance) >= self._threshold)
            .order_by(distance)
            .limit(1)
        )

        row = self._db.execute(stmt).fetchone()

        if row is None:
            return None

        # Increment hit count
        self._db.execute(
            update(SemanticCacheModel)
            .where(SemanticCacheModel.id == row[0])
            .values(hit_count=SemanticCacheModel.hit_count + 1)
        )
        self._db.add(SemanticCacheHit(id=str(uuid.uuid4()), cache_id=row[0]))
        self._db.commit()

        return {
            "response": row[1],
            "citations": row[2] if row[2] is not None else [],
        }

    async def store(
        self,
        query: str,
        response: str,
        citations: list[Citation],
        doc_ids: list[str],
        chunk_ids: list[str],
    ) -> None:
        embedding = await self._client.embed_query(query)
        citations_data = [c.model_dump() for c in citations]
        row = SemanticCacheModel(
            id=str(uuid.uuid4()),
            query_embedding=embedding,
            query_text=query,
            response_json=response,
            citations_json=citations_data,
            source_document_ids=doc_ids,
            source_chunk_ids=chunk_ids,
            hit_count=0,
        )
        self._db.add(row)
        self._db.commit()

    async def invalidate_by_document(self, doc_id: str) -> None:
        invalidate_cache_for_document(self._db, doc_id)


def invalidate_cache_for_document(db: Session, doc_id: str, *, commit: bool = True) -> None:
    """Delete semantic cache entries that reference the given document."""
    db.execute(
        text(
            "DELETE FROM semantic_cache "
            "WHERE source_document_ids::jsonb @> CAST(:doc_id_json AS jsonb)"
        ),
        {"doc_id_json": json.dumps([doc_id])},
    )
    if commit:
        db.commit()
