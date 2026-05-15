from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models import Citation
from app.services.semantic_cache import SemanticCache
from tests.conftest import FAKE_EMBEDDING


class _MockProvider:
    async def embed_query(self, query: str) -> list[float]:
        return FAKE_EMBEDDING

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [FAKE_EMBEDDING for _ in texts]


def _make_cache(db: MagicMock | None = None) -> SemanticCache:
    return SemanticCache(
        db=db or MagicMock(),
        embedding_client=_MockProvider(),
        threshold=0.92,
    )


def _make_citation() -> Citation:
    return Citation(filename="doc.pdf", page_number=1, excerpt="text", score=0.9)


@pytest.mark.asyncio
async def test_lookup_hit() -> None:
    db = MagicMock()
    # Simulate a matching row: (id, response_json, citations_json)
    fake_row = ("row-id-1", "This is the answer.", [{"filename": "doc.pdf"}])
    db.execute.return_value.fetchone.return_value = fake_row

    cache = _make_cache(db=db)
    result = await cache.lookup("what is X?")

    assert result is not None
    assert result["response"] == "This is the answer."
    assert isinstance(result["citations"], list)
    # Hit count update was called
    assert db.execute.call_count == 2


@pytest.mark.asyncio
async def test_lookup_hit_records_cache_hit_event() -> None:
    db = MagicMock()
    fake_row = ("row-id-1", "This is the answer.", [{"filename": "doc.pdf"}])
    db.execute.return_value.fetchone.return_value = fake_row

    cache = _make_cache(db=db)
    await cache.lookup("what is X?")

    assert db.add.call_count == 1
    added_row = db.add.call_args[0][0]
    assert added_row.cache_id == "row-id-1"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_lookup_miss() -> None:
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None

    cache = _make_cache(db=db)
    result = await cache.lookup("unknown query")

    assert result is None


@pytest.mark.asyncio
async def test_store() -> None:
    db = MagicMock()
    cache = _make_cache(db=db)

    await cache.store(
        query="test query",
        response="test answer",
        citations=[_make_citation()],
        doc_ids=["doc-1"],
        chunk_ids=["chunk-1"],
    )

    db.add.assert_called_once()
    db.commit.assert_called_once()

    added_row = db.add.call_args[0][0]
    assert added_row.query_text == "test query"
    assert added_row.response_json == "test answer"
    assert added_row.source_document_ids == ["doc-1"]
    assert added_row.source_chunk_ids == ["chunk-1"]


@pytest.mark.asyncio
async def test_invalidate_by_document() -> None:
    db = MagicMock()
    cache = _make_cache(db=db)

    await cache.invalidate_by_document("doc-42")

    db.execute.assert_called_once()
    call_args = db.execute.call_args
    # Verify the doc_id is in the bind params
    params = call_args[0][1]
    assert "doc-42" in params["doc_id_json"]
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_lookup_uses_vector_distance_expression() -> None:
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = None
    cache = _make_cache(db=db)

    await cache.lookup("what is X?")

    stmt = db.execute.call_args[0][0]
    sql = str(stmt)
    assert "semantic_cache.query_embedding" in sql
    assert "<=>" in sql
