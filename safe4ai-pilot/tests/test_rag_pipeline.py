from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import RankedChunk, RetrievedChunk
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
    embedding_client: MagicMock | None = None,
) -> RagPipeline:
    r = retriever or MagicMock()
    rr = reranker or MagicMock()
    d = db or MagicMock()
    # Always inject a mock embedding_client so tests never create a live
    # OllamaProvider (which would attempt real HTTP calls to Ollama).
    ec = embedding_client or MagicMock()
    ec.embed_documents = getattr(ec, "embed_documents", None) or AsyncMock(
        return_value=[FAKE_EMBEDDING]
    )

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
            embedding_client=ec,
        )
    return pipeline


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
        patch("app.services.document_parser.PdfReader", return_value=mock_reader),
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
        patch("app.services.document_parser.PdfReader", return_value=mock_reader),
        patch("app.services.document_parser.convert_from_path", return_value=[fake_image]),
        patch("app.services.document_parser.ocr_page", new=AsyncMock(return_value=("ocr text", "low"))),
        patch.object(pipeline, "_embed_batch", new=AsyncMock(return_value=[FAKE_EMBEDDING])),
        patch.object(pipeline, "_retriever") as mock_retriever,
    ):
        mock_retriever.update_bm25_index = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF fake")
            tmp_path = f.name

        await pipeline.ingest(tmp_path, "doc-1", "test.pdf", "user-1")

    # Low-confidence OCR pages still result in indexed status — chunks are in Qdrant.
    db.get.assert_called()
    assert mock_doc.ingestion_status == "indexed"


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
        patch("app.services.document_parser.PdfReader", return_value=mock_reader),
        patch("app.services.document_parser.convert_from_path", return_value=[fake_image]),
        patch("app.services.document_parser.ocr_page", new=AsyncMock(return_value=("ocr text", "medium"))),
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
        patch("app.services.document_parser.PdfReader", return_value=mock_reader),
        patch.object(pipeline, "_embed_batch", new=AsyncMock(return_value=[FAKE_EMBEDDING])),
        patch.object(pipeline, "_retriever") as mock_retriever,
    ):
        mock_retriever.update_bm25_index = MagicMock()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF fake")
            tmp_path = f.name
        await pipeline.ingest(tmp_path, "doc-1", "test.pdf", "user-1")


# ---------------------------------------------------------------------------
# Split-client tests: each client routes to the correct provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_batch_uses_embedding_client_not_chat_client() -> None:
    """embedding_client.embed_documents is called; chat_client is never touched."""
    chat_client = MagicMock()
    embedding_client = MagicMock()
    embedding_client.embed_documents = AsyncMock(return_value=[FAKE_EMBEDDING])

    with patch("app.services.rag_pipeline.QdrantClient"):
        pipeline = RagPipeline(
            retriever=MagicMock(),
            reranker=MagicMock(),
            ollama_url="http://localhost:11434",
            ollama_model="qwen3.5:9b",
            embedding_model="nomic-embed-text",
            qdrant_url="http://localhost:6333",
            collection="test",
            db_session=MagicMock(),
            chat_client=chat_client,
            embedding_client=embedding_client,
        )

    # Set up the negative assertion BEFORE the call so we can verify it was never touched.
    chat_client.embed_documents = MagicMock()

    result = await pipeline._embed_batch(["hello"])

    embedding_client.embed_documents.assert_awaited_once_with(["hello"])
    chat_client.embed_documents.assert_not_called()
    chat_client.chat.assert_not_called()
    assert result == [FAKE_EMBEDDING]


@pytest.mark.asyncio
async def test_generate_uses_chat_client_not_embedding_client() -> None:
    """chat_client.chat is called; embedding_client is never touched."""
    chat_result = MagicMock()
    chat_result.content = "The answer is 42."

    chat_client = MagicMock()
    chat_client.chat = AsyncMock(return_value=chat_result)

    embedding_client = MagicMock()
    embedding_client.embed_documents = AsyncMock(return_value=[FAKE_EMBEDDING])

    with patch("app.services.rag_pipeline.QdrantClient"):
        pipeline = RagPipeline(
            retriever=MagicMock(),
            reranker=MagicMock(),
            ollama_url="http://localhost:11434",
            ollama_model="qwen3.5:9b",
            embedding_model="nomic-embed-text",
            qdrant_url="http://localhost:6333",
            collection="test",
            db_session=MagicMock(),
            chat_client=chat_client,
            embedding_client=embedding_client,
        )

    answer = await pipeline._generate("What is 6 * 7?")

    chat_client.chat.assert_awaited_once()
    embedding_client.embed_documents.assert_not_awaited()
    assert answer == "The answer is 42."


@pytest.mark.asyncio
async def test_ocr_page_uses_vision_client_not_chat_client() -> None:
    """vision_client.describe_image is called; chat_client is never touched."""
    vision_client = MagicMock()
    vision_client.describe_image = AsyncMock(side_effect=["extracted text", "high confidence"])

    chat_client = MagicMock()
    chat_client.chat = AsyncMock()

    import os
    import tempfile

    with patch("app.services.rag_pipeline.QdrantClient"):
        pipeline = RagPipeline(
            retriever=MagicMock(),
            reranker=MagicMock(),
            ollama_url="http://localhost:11434",
            ollama_model="qwen3.5:9b",
            embedding_model="nomic-embed-text",
            qdrant_url="http://localhost:6333",
            collection="test",
            db_session=MagicMock(),
            chat_client=chat_client,
            vision_client=vision_client,
        )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        tmp_path = f.name

    try:
        text, quality = await pipeline._ocr_page(tmp_path)
    finally:
        os.unlink(tmp_path)

    vision_client.describe_image.assert_awaited()
    chat_client.chat.assert_not_awaited()
    assert text == "extracted text"
