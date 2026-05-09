from __future__ import annotations

import uuid
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import SemanticCache as SemanticCacheModel
from app.models import Citation


class SemanticCache:
    def __init__(
        self,
        db: Session,
        ollama_url: str,
        embedding_model: str,
        threshold: float,
    ) -> None:
        self._db = db
        self._ollama_url = ollama_url
        self._embedding_model = embedding_model
        self._threshold = threshold

    async def _embed(self, query: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._ollama_url}/api/embeddings",
                json={"model": self._embedding_model, "prompt": query},
                timeout=30.0,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            embedding = data.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError("Ollama embeddings response did not include an embedding list")
            return [float(value) for value in embedding]

    async def lookup(self, query: str) -> dict[str, Any] | None:
        embedding = await self._embed(query)
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

        row = self._db.execute(
            text(
                "SELECT id, response_json, citations_json "
                "FROM semantic_cache "
                "WHERE 1 - (query_embedding <=> CAST(:embedding AS vector)) >= :threshold "
                "ORDER BY query_embedding <=> CAST(:embedding AS vector) "
                "LIMIT 1"
            ),
            {"embedding": embedding_str, "threshold": self._threshold},
        ).fetchone()

        if row is None:
            return None

        # Increment hit count
        self._db.execute(
            text("UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE id = :id"),
            {"id": row[0]},
        )
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
        embedding = await self._embed(query)
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
        # Delete rows where doc_id appears in source_document_ids JSON array
        self._db.execute(
            text(
                "DELETE FROM semantic_cache "
                "WHERE source_document_ids::jsonb @> CAST(:doc_id_json AS jsonb)"
            ),
            {"doc_id_json": f'["{doc_id}"]'},
        )
        self._db.commit()
