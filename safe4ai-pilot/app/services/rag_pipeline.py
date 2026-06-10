from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import structlog
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy.orm import Session

from app.agents.llm_caller import call_llm
from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.db.models import Document, DocumentChunk, IngestionStatus
from app.security.content_filter import ContentFilter
from app.services import document_parser
from app.services.provider_clients import ChatClient, EmbeddingClient, OllamaProvider, VisionClient

logger = structlog.get_logger(__name__)

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 150
_EMBED_BATCH = 100
_MIN_RERANK_SCORE = 0.45


class RagPipeline:
    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: Reranker,
        ollama_url: str,
        ollama_model: str,
        embedding_model: str,
        qdrant_url: str,
        collection: str,
        db_session: Session,
        *,
        chat_client: ChatClient | None = None,
        embedding_client: EmbeddingClient | None = None,
        vision_client: VisionClient | None = None,
        chunk_size: int = _CHUNK_SIZE,
        chunk_overlap: int = _CHUNK_OVERLAP,
        rerank_top_n: int = 6,
        min_rerank_score: float = _MIN_RERANK_SCORE,
        vision_model: str | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        self._embedding_model = embedding_model
        self._qdrant = QdrantClient(url=qdrant_url)
        self._collection = collection
        self._db = db_session
        self._chat_client = chat_client
        # Always resolve to a concrete EmbeddingClient so _embed_batch never
        # needs inline HTTP code. OllamaProvider is created as a fallback when
        # no client is supplied — callers can still inject any EmbeddingClient.
        self._embedding_client: EmbeddingClient = embedding_client or OllamaProvider(
            base_url=ollama_url,
            chat_model=ollama_model,
            embedding_model=embedding_model,
            vision_model=vision_model or "",
        )
        self._vision_client = vision_client
        self._rerank_top_n = rerank_top_n
        self._min_rerank_score = min_rerank_score
        self._vision_model = vision_model
        self._content_filter = ContentFilter()
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest(
        self,
        file_path: str,
        doc_id: str,
        filename: str,
        uploaded_by: str,
        *,
        document_version: int = 1,
        activate: bool = True,
    ) -> None:
        """Parse, chunk, embed, and index a document.

        With ``activate=False`` the chunks are ingested as a staged version:
        they carry ``is_active=False`` in Qdrant (excluded from retrieval) and
        are not added to BM25. The caller switches the active version after a
        successful ingest — see ingestion_service.run_ingestion.
        """
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            pages, low_confidence_count = await self._load_pdf(file_path)
        elif ext == ".docx":
            pages = document_parser.load_docx(file_path)
            low_confidence_count = 0
        elif ext == ".xlsx":
            pages = document_parser.load_xlsx(file_path)
            low_confidence_count = 0
        else:
            text = Path(file_path).read_text(encoding="utf-8", errors="replace")
            pages = [(text, 0, "native")]
            low_confidence_count = 0

        # Chunk all pages
        all_chunks: list[dict[str, Any]] = []
        for text, page_number, ocr_quality in pages:
            if not text.strip():
                continue
            splits = self._splitter.split_text(text)
            for idx, split in enumerate(splits):
                all_chunks.append(
                    {
                        "content": split,
                        "page_number": page_number,
                        "chunk_index": idx,
                        "ocr_quality": ocr_quality,
                    }
                )

        if not all_chunks:
            self._set_status(doc_id, IngestionStatus.failed)
            self._db.commit()
            return

        for chunk in all_chunks:
            if self._content_filter.is_pii(chunk["content"]):
                chunk["content"] = self._content_filter.redact(chunk["content"])
                logger.info("pii_redacted_in_chunk", doc_id=doc_id, page=chunk.get("page_number"))

        contents = [c["content"] for c in all_chunks]
        embeddings = await self._embed_batch(contents)

        chunk_ids = [str(uuid.uuid4()) for _ in all_chunks]
        points = [
            qmodels.PointStruct(
                id=chunk_ids[i],
                vector=embeddings[i],
                payload={
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_number": all_chunks[i]["page_number"],
                    "chunk_index": all_chunks[i]["chunk_index"],
                    "content": all_chunks[i]["content"],
                    "ocr_quality": all_chunks[i]["ocr_quality"],
                    "doc_version": document_version,
                    "is_active": activate,
                },
            )
            for i in range(len(all_chunks))
        ]

        self._qdrant.upsert(collection_name=self._collection, points=points)

        # Persist DocumentChunk rows — same UUID used for both DB id and Qdrant point id
        for i, point in enumerate(points):
            chunk = DocumentChunk(
                id=chunk_ids[i],
                document_id=doc_id,
                chunk_index=all_chunks[i]["chunk_index"],
                chunk_version=document_version,
                content_preview=all_chunks[i]["content"][:200],
                qdrant_point_id=chunk_ids[i],
            )
            self._db.add(chunk)

        # Update document status
        total_pages = len(pages)
        # Even with low OCR confidence, chunks are already in Qdrant — mark as indexed.
        # Low-confidence pages are detectable via the ocr_quality payload field in Qdrant.
        self._set_status(doc_id, IngestionStatus.indexed)
        self._db.commit()

        # Update BM25 index — staged versions join BM25 only at activation
        if activate:
            payloads = [point.payload or {} for point in points]
            self._retriever.update_bm25_index(chunk_ids, contents, payloads)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* in slices of _EMBED_BATCH via the stored embedding client."""
        results: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i : i + _EMBED_BATCH]
            results.extend(await self._embedding_client.embed_documents(batch))
        return results

    async def _generate(self, prompt: str) -> str:
        """Generate an answer via the configured LLM."""
        return await call_llm(
            prompt,
            system="Answer using retrieved context.",
            chat_client=self._chat_client,
            ollama_url=self._ollama_url,
            model=self._ollama_model,
            timeout=120.0,
        )

    async def _load_pdf(self, file_path: str) -> tuple[list[document_parser.Page], int]:
        """Delegate to document_parser.load_pdf (kept for test patching compatibility)."""
        return await document_parser.load_pdf(
            file_path,
            vision_client=self._vision_client,
            vision_model=self._vision_model,
            ollama_url=self._ollama_url,
        )

    async def _ocr_page(self, image_path: str) -> tuple[str, str]:
        """Delegate to document_parser.ocr_page (kept for test patching compatibility)."""
        return await document_parser.ocr_page(
            image_path,
            vision_client=self._vision_client,
            vision_model=self._vision_model,
            ollama_url=self._ollama_url,
        )

    def _set_status(self, doc_id: str, status: IngestionStatus) -> None:
        doc = self._db.get(Document, doc_id)
        if doc is not None:
            setattr(doc, "ingestion_status", status)
