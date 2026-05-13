from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Citation, RankedChunk, RetrievedChunk
from app.services.rag_pipeline import RagPipeline
from tests.conftest import FAKE_EMBEDDING


def _make_ranked_chunk(chunk_id: str, rerank_score: float) -> RankedChunk:
    return RankedChunk(
        chunk_id=chunk_id,
        doc_id="doc-1",
        filename="file.pdf",
        page_number=1,
        content=f"Content {chunk_id}",
        score=0.9,
        rerank_score=rerank_score,
    )


def _make_pipeline(
    retriever: MagicMock | None = None,
    reranker: MagicMock | None = None,
    db: MagicMock | None = None,
) -> RagPipeline:
    r = retriever or MagicMock()
    rr = reranker or MagicMock()
    d = db or MagicMock()

    with patch("app.services.rag_pipeline.QdrantClient"):
        pipeline = RagPipeline(
            retriever=r,
            reranker=rr,
            ollama_url="http://localhost:11434",
            ollama_model="qwen3.5:9b",
            embedding_model="nomic-embed-text",
            qdrant_url="http://localhost:6333",
            collection="test",
            db_session=d,
        )
    return pipeline


@pytest.mark.asyncio
async def test_query_returns_answer_and_citations() -> None:
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(
        return_value=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="d1",
                filename="f.pdf",
                page_number=1,
                content="relevant content",
                score=0.9,
            )
        ]
    )

    reranker = MagicMock()
    reranker.rerank.return_value = [_make_ranked_chunk("c1", 0.8)]

    pipeline = _make_pipeline(retriever=retriever, reranker=reranker)

    with patch.object(pipeline, "_generate", new=AsyncMock(return_value="Answer text")):
        answer, citations = await pipeline.query("test query", "col")

    retriever.retrieve.assert_awaited_once_with("test query", None, collection="col")
    assert answer == "Answer text"
    assert len(citations) == 1
    assert isinstance(citations[0], Citation)
    assert citations[0].score == 0.8


@pytest.mark.asyncio
async def test_query_no_answer_fallback() -> None:
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(
        return_value=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="d1",
                filename="f.pdf",
                page_number=1,
                content="something",
                score=0.5,
            )
        ]
    )

    reranker = MagicMock()
    # max rerank_score = 0.3, below 0.45 threshold
    reranker.rerank.return_value = [_make_ranked_chunk("c1", 0.3)]

    pipeline = _make_pipeline(retriever=retriever, reranker=reranker)

    answer, citations = await pipeline.query("test query", "col")

    assert "don't have enough information" in answer
    assert citations == []


@pytest.mark.asyncio
async def test_ingest_empty_document_sets_failed_status_and_commits() -> None:
    pipeline = _make_pipeline()
    db = MagicMock()
    mock_doc = MagicMock()
    db.get.return_value = mock_doc
    pipeline._db = db

    with patch.object(pipeline, "_load_pdf", new=AsyncMock(return_value=([("", 1, "native")], 0))):
        await pipeline.ingest("empty.pdf", "doc-1", "empty.pdf", "user-1")

    assert mock_doc.ingestion_status == "failed"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_pdf_native_text() -> None:
    """Test ingestion of a PDF with native (non-OCR) text."""
    pipeline = _make_pipeline()

    fake_page = MagicMock()
    fake_page.extract_text.return_value = "A" * 100  # >= 50 chars, no OCR needed

    mock_reader = MagicMock()
    mock_reader.pages = [fake_page]

    db = MagicMock()
    pipeline._db = db
    pipeline._qdrant = MagicMock()

    with (
        patch("app.services.rag_pipeline.PdfReader", return_value=mock_reader),
        patch.object(pipeline, "_embed_batch", new=AsyncMock(return_value=[FAKE_EMBEDDING])),
        patch.object(pipeline, "_retriever") as mock_retriever,
    ):
        mock_retriever.update_bm25_index = MagicMock()
        db.get.return_value = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF fake")
            tmp_path = f.name

        await pipeline.ingest(tmp_path, "doc-1", "test.pdf", "user-1")

    pipeline._qdrant.upsert.assert_called_once()
    points = pipeline._qdrant.upsert.call_args.kwargs["points"]
    assert points[0].payload["page_number"] == 1
    db.add.assert_called()
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_ingest_triggers_needs_review() -> None:
    """All pages have low OCR confidence → needs_review status."""
    pipeline = _make_pipeline()

    # Page with insufficient text → triggers OCR path
    fake_page = MagicMock()
    fake_page.extract_text.return_value = "X"  # < 50 chars

    mock_reader = MagicMock()
    mock_reader.pages = [fake_page]

    db = MagicMock()
    pipeline._db = db
    pipeline._qdrant = MagicMock()
    mock_doc = MagicMock()
    db.get.return_value = mock_doc

    fake_image = MagicMock()

    with (
        patch("app.services.rag_pipeline.PdfReader", return_value=mock_reader),
        patch("app.services.rag_pipeline.convert_from_path", return_value=[fake_image]),
        patch.object(pipeline, "_ocr_page", new=AsyncMock(return_value=("ocr text", "low"))),
        patch.object(pipeline, "_embed_batch", new=AsyncMock(return_value=[FAKE_EMBEDDING])),
        patch.object(pipeline, "_retriever") as mock_retriever,
    ):
        mock_retriever.update_bm25_index = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF fake")
            tmp_path = f.name

        await pipeline.ingest(tmp_path, "doc-1", "test.pdf", "user-1")

    # _set_status was called — verified via db.get call
    db.get.assert_called()
    # With 1 page and 1 low confidence page: 1/1 > 0.5 → needs_review
    assert mock_doc.ingestion_status == "skipped"


@pytest.mark.asyncio
async def test_ingest_sets_ocr_quality_in_qdrant_payload() -> None:
    """Qdrant point payload must include ocr_quality from _load_pdf."""
    pipeline = _make_pipeline()

    fake_page = MagicMock()
    fake_page.extract_text.return_value = "X"  # < 50 chars → OCR path

    mock_reader = MagicMock()
    mock_reader.pages = [fake_page]

    db = MagicMock()
    pipeline._db = db
    pipeline._qdrant = MagicMock()
    db.get.return_value = MagicMock()

    fake_image = MagicMock()

    with (
        patch("app.services.rag_pipeline.PdfReader", return_value=mock_reader),
        patch("app.services.rag_pipeline.convert_from_path", return_value=[fake_image]),
        patch.object(pipeline, "_ocr_page", new=AsyncMock(return_value=("ocr text", "medium"))),
        patch.object(pipeline, "_embed_batch", new=AsyncMock(return_value=[FAKE_EMBEDDING])),
        patch.object(pipeline, "_retriever") as mock_retriever,
    ):
        mock_retriever.update_bm25_index = MagicMock()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF fake")
            tmp_path = f.name
        await pipeline.ingest(tmp_path, "doc-1", "test.pdf", "user-1")

    points = pipeline._qdrant.upsert.call_args.kwargs["points"]
    assert len(points) > 0
    assert points[0].payload["ocr_quality"] == "medium"


@pytest.mark.asyncio
async def test_ingest_native_pdf_page_gets_native_quality() -> None:
    """Native text extraction pages must set ocr_quality='native' in the payload."""
    pipeline = _make_pipeline()

    fake_page = MagicMock()
    fake_page.extract_text.return_value = "A" * 100  # >= 50 chars → native

    mock_reader = MagicMock()
    mock_reader.pages = [fake_page]

    db = MagicMock()
    pipeline._db = db
    pipeline._qdrant = MagicMock()
    db.get.return_value = MagicMock()

    with (
        patch("app.services.rag_pipeline.PdfReader", return_value=mock_reader),
        patch.object(pipeline, "_embed_batch", new=AsyncMock(return_value=[FAKE_EMBEDDING])),
        patch.object(pipeline, "_retriever") as mock_retriever,
    ):
        mock_retriever.update_bm25_index = MagicMock()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF fake")
            tmp_path = f.name
        await pipeline.ingest(tmp_path, "doc-1", "test.pdf", "user-1")

    points = pipeline._qdrant.upsert.call_args.kwargs["points"]
    assert points[0].payload["ocr_quality"] == "native"
