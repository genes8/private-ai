from __future__ import annotations

from unittest.mock import patch

import numpy as np

from app.components.reranker import Reranker
from app.models import RankedChunk, RetrievedChunk


def _make_chunk(chunk_id: str, score: float = 1.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id="doc-1",
        filename="file.pdf",
        page_number=1,
        content=f"Content {chunk_id}",
        score=score,
    )


def _make_reranker() -> Reranker:
    with patch("app.components.reranker.CrossEncoder"):
        return Reranker()


def test_rerank_returns_top_n() -> None:
    reranker = _make_reranker()
    chunks = [_make_chunk(f"c{i}") for i in range(10)]
    # Scores: chunk c0 gets highest, descending
    fake_scores = np.array([10.0 - i for i in range(10)])
    with patch.object(reranker._model, "predict", return_value=fake_scores):
        results = reranker.rerank("query", chunks, top_n=6)

    assert len(results) == 6
    assert all(isinstance(r, RankedChunk) for r in results)
    # Sorted descending by rerank_score
    scores = [r.rerank_score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0].chunk_id == "c0"


def test_rerank_fewer_than_top_n() -> None:
    reranker = _make_reranker()
    chunks = [_make_chunk(f"c{i}") for i in range(3)]
    fake_scores = np.array([3.0, 1.0, 2.0])
    with patch.object(reranker._model, "predict", return_value=fake_scores):
        results = reranker.rerank("query", chunks, top_n=6)

    assert len(results) == 3
    assert results[0].rerank_score == 3.0


def test_rerank_empty() -> None:
    reranker = _make_reranker()
    results = reranker.rerank("query", [])
    assert results == []
