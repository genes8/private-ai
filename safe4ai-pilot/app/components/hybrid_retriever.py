from __future__ import annotations

import asyncio
from threading import RLock
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
        self._bm25_lock = RLock()

    def _rebuild_bm25_index(self, entries: list[tuple[str, str, dict[str, Any]]]) -> None:
        if not entries:
            self._bm25 = None
            self._bm25_chunk_ids = []
            self._bm25_payloads = {}
            return

        chunk_ids = [chunk_id for chunk_id, _, _ in entries]
        contents = [content for _, content, _ in entries]
        self._bm25 = BM25Okapi([text.lower().split() for text in contents])
        self._bm25_chunk_ids = chunk_ids
        self._bm25_payloads = {chunk_id: payload for chunk_id, _, payload in entries}

    def update_bm25_index(
        self,
        chunk_ids: list[str],
        contents: list[str],
        payloads: list[dict[str, Any]] | None = None,
    ) -> None:
        """Rebuild BM25 index with the given chunk IDs and their text contents."""
        if not chunk_ids:
            return

        incoming_payloads = (
            list(payloads) if payloads is not None else [{"content": text} for text in contents]
        )
        incoming_entries = [
            (chunk_id, content, payload)
            for chunk_id, content, payload in zip(chunk_ids, contents, incoming_payloads, strict=False)
        ]

        with self._bm25_lock:
            if self._bm25 is None or not self._bm25_chunk_ids:
                self._rebuild_bm25_index(incoming_entries)
                return

            existing_entries: list[tuple[str, str, dict[str, Any]]] = []
            for chunk_id in self._bm25_chunk_ids:
                payload = self._bm25_payloads.get(chunk_id)
                if payload is None:
                    continue
                existing_entries.append(
                    (
                        chunk_id,
                        str(payload.get("content", "")),
                        dict(payload),
                    )
                )

            self._rebuild_bm25_index(existing_entries + incoming_entries)

    def remove_from_bm25(self, doc_id: str) -> None:
        """Remove all BM25 entries for a document and rebuild the sparse index."""
        with self._bm25_lock:
            if self._bm25 is None or not self._bm25_chunk_ids:
                return

            remaining_entries: list[tuple[str, str, dict[str, Any]]] = []
            for chunk_id in self._bm25_chunk_ids:
                payload = self._bm25_payloads.get(chunk_id, {})
                if str(payload.get("doc_id", "")) == doc_id:
                    continue
                remaining_entries.append(
                    (
                        chunk_id,
                        str(payload.get("content", "")),
                        dict(payload),
                    )
                )

            self._rebuild_bm25_index(remaining_entries)

    async def _embed(self, query: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._ollama_url}/api/embed",
                json={"model": self._embedding_model, "input": query},
                timeout=30.0,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            embedding = data.get("embedding") or data.get("embeddings", [None])[0]
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

        response = await asyncio.to_thread(
            self._qdrant.query_points,
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
        with self._bm25_lock:
            bm25 = self._bm25
            bm25_chunk_ids = list(self._bm25_chunk_ids)
            bm25_payloads = dict(self._bm25_payloads)
        if bm25 is not None and bm25_chunk_ids:
            tokenized_query = query.lower().split()
            scores = bm25.get_scores(tokenized_query)
            filtered: list[tuple[int, float, dict[str, Any]]] = []
            for idx, score in enumerate(scores):
                cid = bm25_chunk_ids[idx]
                payload = dense_data.get(cid) or bm25_payloads.get(cid, {})
                if doc_ids and payload.get("doc_id") not in doc_ids:
                    continue
                filtered.append((idx, score, payload))

            indexed = sorted(filtered, key=lambda x: x[1], reverse=True)[:top_k]
            for rank, (idx, _score, payload) in enumerate(indexed, start=1):
                cid = bm25_chunk_ids[idx]
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
