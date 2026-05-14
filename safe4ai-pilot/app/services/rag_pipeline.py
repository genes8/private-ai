from __future__ import annotations

import base64
import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import docx2txt
import httpx
import openpyxl
import structlog
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pdf2image import convert_from_path
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy.orm import Session

from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.db.models import Document, DocumentChunk, IngestionStatus
from app.models import Citation, RankedChunk
from app.security.content_filter import ContentFilter

logger = structlog.get_logger(__name__)

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 150
_EMBED_BATCH = 100
_OCR_THRESHOLD = 50  # chars below which we try vision OCR
_LOW_CONFIDENCE_RATIO = 0.5
_MIN_RERANK_SCORE = 0.45
_NO_ANSWER = "I don't have enough information in the provided documents to answer this question."


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
        chunk_size: int = _CHUNK_SIZE,
        chunk_overlap: int = _CHUNK_OVERLAP,
        rerank_top_n: int = 6,
        min_rerank_score: float = _MIN_RERANK_SCORE,
        vision_model: str = "qwen2.5vl:7b",
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        self._embedding_model = embedding_model
        self._qdrant = QdrantClient(url=qdrant_url)
        self._collection = collection
        self._db = db_session
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
    ) -> None:
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            pages, low_confidence_count = await self._load_pdf(file_path)
        elif ext == ".docx":
            text = docx2txt.process(file_path)
            pages = [(text, 0, "native")]
            low_confidence_count = 0
        elif ext == ".xlsx":
            pages = [(t, p, "native") for t, p in self._load_xlsx(file_path)]
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

        clean_chunks = [c for c in all_chunks if not self._content_filter.is_pii(c["content"])]
        if not clean_chunks:
            self._set_status(doc_id, IngestionStatus.skipped)
            self._db.commit()
            return

        contents = [c["content"] for c in clean_chunks]
        embeddings = await self._embed_batch(contents)

        points = [
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[i],
                payload={
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_number": clean_chunks[i]["page_number"],
                    "chunk_index": clean_chunks[i]["chunk_index"],
                    "content": clean_chunks[i]["content"],
                    "ocr_quality": clean_chunks[i]["ocr_quality"],
                },
            )
            for i in range(len(clean_chunks))
        ]

        self._qdrant.upsert(collection_name=self._collection, points=points)

        # Persist DocumentChunk rows
        for i, point in enumerate(points):
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=clean_chunks[i]["chunk_index"],
                chunk_version=document_version,
                content_preview=clean_chunks[i]["content"][:200],
                qdrant_point_id=str(point.id),
            )
            self._db.add(chunk)

        # Update document status
        total_pages = len(pages)
        needs_review = (
            total_pages > 0 and low_confidence_count / total_pages > _LOW_CONFIDENCE_RATIO
        )
        self._set_status(
            doc_id,
            IngestionStatus.skipped if needs_review else IngestionStatus.indexed,
        )
        self._db.commit()

        # Update BM25 index
        chunk_ids = [str(p.id) for p in points]
        payloads = [point.payload or {} for point in points]
        self._retriever.update_bm25_index(chunk_ids, contents, payloads)

    async def query(
        self,
        query: str,
        collection: str,
        doc_ids: list[str] | None = None,
    ) -> tuple[str, list[Citation]]:
        chunks = await self._retriever.retrieve(query, doc_ids, collection=collection)
        ranked: list[RankedChunk] = self._reranker.rerank(query, chunks, top_n=self._rerank_top_n)

        if not ranked or max(c.rerank_score for c in ranked) < self._min_rerank_score:
            return _NO_ANSWER, []

        citations = [
            Citation(
                filename=c.filename,
                page_number=c.page_number,
                excerpt=c.content[:200],
                score=c.rerank_score,
            )
            for c in ranked
        ]

        context = "\n\n".join(f"[{c.filename} p.{c.page_number}]: {c.content}" for c in ranked)
        prompt = (
            "Answer the following question using ONLY the provided context. "
            "If the context doesn't contain enough information, say so.\n\n"
            f"Context:\n{context}\n\nQuestion: {query}"
        )

        answer = await self._generate(prompt)
        return answer, citations

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        async with httpx.AsyncClient() as client:
            for i in range(0, len(texts), _EMBED_BATCH):
                batch = texts[i : i + _EMBED_BATCH]
                try:
                    resp = await client.post(
                        f"{self._ollama_url}/api/embed",
                        json={"model": self._embedding_model, "input": batch},
                        timeout=120.0,
                    )
                    resp.raise_for_status()
                    body: dict[str, Any] = resp.json()
                    embeddings = body.get("embeddings")
                    if not isinstance(embeddings, list):
                        raise ValueError("Ollama embed response did not include an embeddings list")
                    results.extend([[float(value) for value in embedding] for embedding in embeddings])
                    continue
                except (httpx.HTTPStatusError, ValueError, TypeError):
                    responses = await asyncio.gather(
                        *[
                            client.post(
                                f"{self._ollama_url}/api/embeddings",
                                json={"model": self._embedding_model, "prompt": text},
                                timeout=60.0,
                            )
                            for text in batch
                        ]
                    )
                    for fallback_resp in responses:
                        fallback_resp.raise_for_status()
                        fallback_body: dict[str, Any] = fallback_resp.json()
                        results.append(fallback_body["embedding"])
        return results

    async def _ocr_page(self, image_path: str) -> tuple[str, str]:
        """Returns (text, confidence) where confidence is 'high'|'medium'|'low'."""
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        async with httpx.AsyncClient() as client:
            # Extract text
            extract_resp = await client.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": self._vision_model,
                    "prompt": (
                        "Extract all text from this document page exactly as it appears. "
                        "Preserve structure, headers, tables, and lists. "
                        "Return only the extracted text."
                    ),
                    "images": [b64],
                    "stream": False,
                },
                timeout=120.0,
            )
            extract_resp.raise_for_status()
            text: str = extract_resp.json().get("response", "")

            # Quality gate
            quality_resp = await client.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": self._vision_model,
                    "prompt": (
                        "Rate your confidence in the text extraction: high/medium/low. "
                        'Return JSON {"confidence": "...", "reason": "..."}.'
                    ),
                    "images": [b64],
                    "stream": False,
                },
                timeout=60.0,
            )
            quality_resp.raise_for_status()
            quality_raw: str = quality_resp.json().get("response", "{}")
            try:
                quality_data: dict[str, Any] = json.loads(quality_raw)
                confidence: str = quality_data.get("confidence", "low")
            except (json.JSONDecodeError, AttributeError):
                confidence = "low"

        return text, confidence

    async def _generate(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": self._ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return str(resp.json().get("response", ""))

    async def _load_pdf(self, file_path: str) -> tuple[list[tuple[str, int, str]], int]:
        """Returns (pages, low_confidence_count). pages is list of (text, page_num, ocr_quality)."""
        reader = PdfReader(file_path)
        pages: list[tuple[str, int, str]] = []
        low_confidence_count = 0

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) >= _OCR_THRESHOLD:
                pages.append((text, page_num, "native"))
            else:
                # Try vision OCR via pdf2image
                try:
                    images = convert_from_path(
                        file_path, dpi=200, first_page=page_num, last_page=page_num
                    )
                    if images:
                        tmp_path = ""
                        try:
                            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                                images[0].save(tmp.name, "PNG")
                                tmp_path = tmp.name
                            ocr_text, confidence = await self._ocr_page(tmp_path)
                        finally:
                            if tmp_path and os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                        pages.append((ocr_text, page_num, confidence))
                        if confidence == "low":
                            low_confidence_count += 1
                    else:
                        pages.append((text, page_num, "low"))
                        low_confidence_count += 1
                except Exception as exc:
                    logger.warning(
                        "pdf_page_ocr_failed",
                        file_path=file_path,
                        page_number=page_num,
                        error=str(exc),
                    )
                    pages.append((text, page_num, "low"))
                    low_confidence_count += 1

        return pages, low_confidence_count

    def _load_xlsx(self, file_path: str) -> list[tuple[str, int]]:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        try:
            pages: list[tuple[str, int]] = []
            for sheet_idx, sheet in enumerate(wb.worksheets, start=1):
                rows: list[str] = []
                for row in sheet.iter_rows(values_only=True):
                    row_str = "\t".join(str(cell) if cell is not None else "" for cell in row)
                    if row_str.strip():
                        rows.append(row_str)
                pages.append(("\n".join(rows), sheet_idx))
            return pages
        finally:
            wb.close()

    def _set_status(self, doc_id: str, status: IngestionStatus) -> None:
        doc = self._db.get(Document, doc_id)
        if doc is not None:
            setattr(doc, "ingestion_status", status)
