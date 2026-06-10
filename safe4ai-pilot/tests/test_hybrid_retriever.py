from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.components.hybrid_retriever import HybridRetriever
from app.models import RetrievedChunk
from tests.conftest import FAKE_EMBEDDING

QDRANT_URL = "http://localhost:6333"
COLLECTION = "test_collection"


class _MockProvider:
    async def embed_query(self, query: str) -> list[float]:
        return FAKE_EMBEDDING

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [FAKE_EMBEDDING for _ in texts]


def _make_retriever() -> HybridRetriever:
    with patch("app.components.hybrid_retriever.QdrantClient"):
        return HybridRetriever(
            qdrant_url=QDRANT_URL,
            collection=COLLECTION,
            embedding_model="nomic-embed-text",
            embedding_client=_MockProvider(),
        )


def _make_hit(chunk_id: str, doc_id: str, score: float = 1.0) -> MagicMock:
    hit = MagicMock()
    hit.id = chunk_id
    hit.score = score
    hit.payload = {
        "doc_id": doc_id,
        "filename": "doc.pdf",
        "page_number": 1,
        "content": f"Content for {chunk_id}",
    }
    return hit


def _make_query_response(hits: list[MagicMock]) -> MagicMock:
    response = MagicMock()
    response.points = hits
    return response


def _make_payload(chunk_id: str, doc_id: str) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "filename": "doc.pdf",
        "page_number": 1,
        "content": f"Content for {chunk_id}",
    }


@pytest.mark.asyncio
async def test_retrieve_returns_rrf_fused_results() -> None:
    retriever = _make_retriever()
    retriever.update_bm25_index(
        ["chunk-1", "chunk-2"],
        ["hello world document", "foo bar document"],
    )

    dense_hits = [_make_hit("chunk-1", "doc-1", 0.9), _make_hit("chunk-2", "doc-1", 0.7)]

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response(dense_hits)
        results = await retriever.retrieve("hello world")

    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(r, RetrievedChunk) for r in results)
    chunk_ids = [r.chunk_id for r in results]
    assert "chunk-1" in chunk_ids


@pytest.mark.asyncio
async def test_retrieve_with_doc_id_filter() -> None:
    retriever = _make_retriever()

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response([])
        await retriever.retrieve("query", doc_ids=["doc-42"])

        call_kwargs: dict[str, Any] = mock_qdrant.query_points.call_args.kwargs
        assert call_kwargs["query_filter"] is not None
        must = call_kwargs["query_filter"].must
        assert len(must) == 1
        assert must[0].key == "doc_id"


@pytest.mark.asyncio
async def test_update_bm25_index() -> None:
    retriever = _make_retriever()
    assert retriever._bm25 is None

    retriever.update_bm25_index(["c1", "c2"], ["foo bar", "baz qux"])

    assert retriever._bm25 is not None
    assert retriever._bm25_chunk_ids == ["c1", "c2"]

    dense_hits = [_make_hit("c1", "d1", 0.8)]

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response(dense_hits)
        results = await retriever.retrieve("foo bar")

    chunk_ids = [r.chunk_id for r in results]
    assert "c1" in chunk_ids


@pytest.mark.asyncio
async def test_remove_from_bm25_prunes_document_chunks() -> None:
    retriever = _make_retriever()
    retriever.update_bm25_index(
        ["c1", "c2"],
        ["alpha beta", "target words"],
        [_make_payload("c1", "doc-1"), _make_payload("c2", "doc-2")],
    )

    retriever.remove_from_bm25("doc-1")

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response([])
        results = await retriever.retrieve("target words")

    assert [r.chunk_id for r in results] == ["c2"]


@pytest.mark.asyncio
async def test_retrieve_returns_sparse_only_payloads_and_applies_doc_filter() -> None:
    retriever = _make_retriever()
    retriever.update_bm25_index(
        ["c1", "c2"],
        ["alpha", "target words"],
        [_make_payload("c1", "doc-1"), _make_payload("c2", "doc-2")],
    )

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response([])
        results = await retriever.retrieve("target words", doc_ids=["doc-2"])

    assert [r.chunk_id for r in results] == ["c2"]
    assert results[0].doc_id == "doc-2"
    assert results[0].content == "Content for c2"


@pytest.mark.asyncio
async def test_retrieve_uses_requested_collection() -> None:
    retriever = _make_retriever()

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response([])
        await retriever.retrieve("query", collection="routed_collection")

    assert mock_qdrant.query_points.call_args.kwargs["collection_name"] == "routed_collection"


@pytest.mark.asyncio
async def test_retrieve_empty_collection() -> None:
    retriever = _make_retriever()

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response([])
        results = await retriever.retrieve("query with no results")

    assert results == []


def test_embedding_model_attribute_exposed() -> None:
    retriever = _make_retriever()
    assert retriever.embedding_model == "nomic-embed-text"


@pytest.mark.asyncio
async def test_retrieve_always_excludes_superseded_versions_in_qdrant_filter() -> None:
    retriever = _make_retriever()

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response([])
        await retriever.retrieve("query")

        qdrant_filter = mock_qdrant.query_points.call_args.kwargs["query_filter"]
        assert qdrant_filter is not None
        assert qdrant_filter.must_not is not None
        assert qdrant_filter.must_not[0].key == "is_active"


@pytest.mark.asyncio
async def test_bm25_path_skips_inactive_chunks() -> None:
    retriever = _make_retriever()
    active_payload = {**_make_payload("c-active", "doc-1"), "is_active": True}
    stale_payload = {**_make_payload("c-stale", "doc-1"), "is_active": False}
    retriever.update_bm25_index(
        ["c-active", "c-stale"],
        ["refund policy thirty days", "refund policy sixty days"],
        [active_payload, stale_payload],
    )

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _make_query_response([])
        results = await retriever.retrieve("refund policy")

    chunk_ids = [r.chunk_id for r in results]
    assert "c-active" in chunk_ids
    assert "c-stale" not in chunk_ids


def test_rebuild_from_qdrant_skips_inactive_points() -> None:
    retriever = _make_retriever()
    active = MagicMock()
    active.id = "c-active"
    active.payload = {**_make_payload("c-active", "doc-1"), "is_active": True}
    stale = MagicMock()
    stale.id = "c-stale"
    stale.payload = {**_make_payload("c-stale", "doc-1"), "is_active": False}

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.scroll.return_value = ([active, stale], None)
        count = retriever.rebuild_from_qdrant()

    assert count == 1
    assert retriever._bm25_chunk_ids == ["c-active"]
