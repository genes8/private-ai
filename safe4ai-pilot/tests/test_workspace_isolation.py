"""Cross-workspace retrieval isolation — the security-critical invariant.

A member of workspace A must never retrieve a chunk in workspace B, on the dense
path OR the sparse (BM25) path, and an empty workspace list must fail closed.
These tests exercise HybridRetriever.retrieve directly with a mocked Qdrant.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.components.hybrid_retriever import HybridRetriever
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


def _payload(chunk_id: str, doc_id: str, workspace_id: str | None) -> dict[str, Any]:
    payload = {
        "doc_id": doc_id,
        "filename": "doc.pdf",
        "page_number": 1,
        "content": f"Content for {chunk_id}",
    }
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    return payload


def _empty_response() -> MagicMock:
    response = MagicMock()
    response.points = []
    return response


@pytest.mark.asyncio
async def test_dense_filter_includes_workspace_constraint() -> None:
    retriever = _make_retriever()
    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _empty_response()
        await retriever.retrieve("q", workspace_ids=["ws-a"])

    qdrant_filter = mock_qdrant.query_points.call_args.kwargs["query_filter"]
    must = qdrant_filter.must or []
    ws_conditions = [c for c in must if getattr(c, "key", None) == "workspace_id"]
    assert ws_conditions, "dense query must filter on workspace_id"
    assert ws_conditions[0].match.any == ["ws-a"]


@pytest.mark.asyncio
async def test_bm25_does_not_leak_other_workspace() -> None:
    """A keyword present only in workspace B must not surface for a workspace-A query."""
    retriever = _make_retriever()
    retriever.update_bm25_index(
        ["c-a", "c-b"],
        ["shared keyword alpha", "shared keyword beta"],
        [_payload("c-a", "doc-a", "ws-a"), _payload("c-b", "doc-b", "ws-b")],
    )

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _empty_response()
        results = await retriever.retrieve("shared keyword", workspace_ids=["ws-a"])

    chunk_ids = [r.chunk_id for r in results]
    assert "c-a" in chunk_ids
    assert "c-b" not in chunk_ids  # workspace B never leaks via the sparse path


@pytest.mark.asyncio
async def test_empty_membership_fails_closed() -> None:
    """A user with zero workspaces retrieves nothing — and never queries Qdrant."""
    retriever = _make_retriever()
    retriever.update_bm25_index(["c-a"], ["alpha"], [_payload("c-a", "doc-a", "ws-a")])

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        results = await retriever.retrieve("alpha", workspace_ids=[])

    assert results == []
    mock_qdrant.query_points.assert_not_called()


@pytest.mark.asyncio
async def test_none_workspace_is_unscoped_for_internal_callers() -> None:
    """workspace_ids=None (trusted internal) adds no workspace filter."""
    retriever = _make_retriever()
    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _empty_response()
        await retriever.retrieve("q", workspace_ids=None)

    qdrant_filter = mock_qdrant.query_points.call_args.kwargs["query_filter"]
    must = qdrant_filter.must or []
    assert not [c for c in must if getattr(c, "key", None) == "workspace_id"]


@pytest.mark.asyncio
async def test_bm25_excludes_chunk_missing_workspace_payload() -> None:
    """Fail-closed: a chunk whose payload lacks workspace_id is not returned when scoped."""
    retriever = _make_retriever()
    retriever.update_bm25_index(
        ["c-legacy"], ["alpha keyword"], [_payload("c-legacy", "doc-x", None)]
    )

    with patch.object(retriever, "_qdrant") as mock_qdrant:
        mock_qdrant.query_points.return_value = _empty_response()
        results = await retriever.retrieve("alpha keyword", workspace_ids=["ws-a"])

    assert results == []
