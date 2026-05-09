from __future__ import annotations

from typing import Any

import httpx
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from rank_bm25 import BM25Okapi

from app.models import RetrievedChunk


class HybridRetriever:
    def __init__(
        self,
        qdrant_url: str,
        collection: str,
        ollama_url: str,
        embedding_model: str,
    ) -> None:
        self._qdrant = QdrantClient(url=qdrant_url)
        self._collection = collection
        self._ollama_url = ollama_url
        self._embedding_model = embedding_model
        self._bm25: BM25Okapi | None = None
        self._bm25_chunk_ids: list[str] = []
        self._bm25_payloads: dict[str, dict[str, Any]] = {}

    def update_bm25_index(
        self,
        chunk_ids: list[str],
        contents: list[str],
        payloads: list[dict[str, Any]] | None = None,
    ) -> None:
        """Rebuild BM25 index with the given chunk IDs and their text contents."""
        tokenized = [text.lower().split() for text in contents]
        self._bm25 = BM25Okapi(tokenized)
        self._bm25_chunk_ids = list(chunk_ids)
        default_payloads = ({"content": text} for text in contents)
        self._bm25_payloads = dict(zip(chunk_ids, payloads or default_payloads))

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

    async def retrieve(
        self,
        query: str,
        doc_ids: list[str] | None = None,
        collection: str | None = None,
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        embedding = await self._embed(query)

        # Build optional qdrant filter for doc_id
        qdrant_filter: qmodels.Filter | None = None
        if doc_ids:
            qdrant_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="doc_id",
                        match=qmodels.MatchAny(any=doc_ids),
                    )
                ]
            )

        response = self._qdrant.query_points(
            collection_name=collection or self._collection,
            query=embedding,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        # Dense rankings: chunk_id -> rank (1-based)
        dense_ranks: dict[str, int] = {}
        dense_data: dict[str, dict[str, Any]] = {}
        for rank, hit in enumerate(response.points, start=1):
            chunk_id = str(hit.id)
            dense_ranks[chunk_id] = rank
            payload = hit.payload or {}
            dense_data[chunk_id] = payload

        # Sparse BM25 rankings
        sparse_ranks: dict[str, int] = {}
        sparse_data: dict[str, dict[str, Any]] = {}
        if self._bm25 is not None and self._bm25_chunk_ids:
            tokenized_query = query.lower().split()
            scores = self._bm25.get_scores(tokenized_query)
            filtered: list[tuple[int, float, dict[str, Any]]] = []
            for idx, score in enumerate(scores):
                cid = self._bm25_chunk_ids[idx]
                payload = dense_data.get(cid) or self._bm25_payloads.get(cid, {})
                if doc_ids and payload.get("doc_id") not in doc_ids:
                    continue
                filtered.append((idx, score, payload))

            indexed = sorted(filtered, key=lambda x: x[1], reverse=True)[:top_k]
            for rank, (idx, _score, payload) in enumerate(indexed, start=1):
                cid = self._bm25_chunk_ids[idx]
                sparse_ranks[cid] = rank
                sparse_data[cid] = payload

        # RRF fusion
        k = 60
        all_ids = set(dense_ranks) | set(sparse_ranks)
        rrf_scores: dict[str, float] = {}
        for cid in all_ids:
            score = 0.0
            if cid in dense_ranks:
                score += 1.0 / (k + dense_ranks[cid])
            if cid in sparse_ranks:
                score += 1.0 / (k + sparse_ranks[cid])
            rrf_scores[cid] = score

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

        results: list[RetrievedChunk] = []
        for cid in sorted_ids:
            payload = dense_data.get(cid) or sparse_data.get(cid) or {}
            results.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_id=str(payload.get("doc_id", "")),
                    filename=str(payload.get("filename", "")),
                    page_number=int(payload.get("page_number", 0)),
                    content=str(payload.get("content", "")),
                    score=rrf_scores[cid],
                )
            )

        return results
