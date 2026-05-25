"""Document parsing utilities: PDF (native + OCR fallback), DOCX, XLSX.

Extracted from RagPipeline so parsing logic can be tested and reused
without instantiating the full pipeline.
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
from typing import Any

import docx2txt
import httpx
import openpyxl
import structlog
from pdf2image import convert_from_path
from pypdf import PdfReader

logger = structlog.get_logger(__name__)

# Chars below which native PDF text is considered too sparse for a page
_OCR_THRESHOLD = 50
# Fraction of single-char words above which text is considered garbled OCR output
_GARBLED_SINGLE_CHAR_RATIO = 0.20

# Return type: list of (text, page_number, ocr_quality) tuples
Page = tuple[str, int, str]


def _is_garbled(text: str) -> bool:
    """Return True when the text looks like garbled OCR output."""
    words = text.split()
    if len(words) < 10:
        return False
    single_char = sum(1 for w in words if len(w) == 1)
    return single_char / len(words) > _GARBLED_SINGLE_CHAR_RATIO


async def ocr_page(
    image_path: str,
    *,
    vision_client: Any = None,
    vision_model: str | None = None,
    ollama_url: str = "",
) -> tuple[str, str]:
    """OCR a single image and return (text, confidence).

    confidence is one of "high" | "medium" | "low".
    """
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    extract_prompt = (
        "Extract all text from this document page exactly as it appears. "
        "Preserve structure, headers, tables, and lists. "
        "Return only the extracted text."
    )
    quality_prompt = (
        "Rate your confidence in the text extraction: high/medium/low. "
        'Return JSON {"confidence": "...", "reason": "..."}.'
    )

    if vision_client is not None and hasattr(vision_client, "describe_image"):
        text = await vision_client.describe_image(extract_prompt, b64)
        quality_raw = await vision_client.describe_image(quality_prompt, b64)
        try:
            quality_data: dict[str, Any] = json.loads(quality_raw)
            confidence: str = quality_data.get("confidence", "low")
        except (json.JSONDecodeError, AttributeError):
            confidence = "low"
        return text, confidence

    if not vision_model:
        raise ValueError("vision_model must be set when vision_client is not provided")
    async with httpx.AsyncClient() as client:
        extract_resp = await client.post(
            f"{ollama_url}/api/generate",
            json={"model": vision_model, "prompt": extract_prompt, "images": [b64], "stream": False},
            timeout=120.0,
        )
        extract_resp.raise_for_status()
        text = extract_resp.json().get("response", "")

        quality_resp = await client.post(
            f"{ollama_url}/api/generate",
            json={"model": vision_model, "prompt": quality_prompt, "images": [b64], "stream": False},
            timeout=60.0,
        )
        quality_resp.raise_for_status()
        quality_raw = quality_resp.json().get("response", "{}")
        try:
            quality_data = json.loads(quality_raw)
            confidence = quality_data.get("confidence", "low")
        except (json.JSONDecodeError, AttributeError):
            confidence = "low"

    return text, confidence


async def load_pdf(
    file_path: str,
    *,
    vision_client: Any = None,
    vision_model: str | None = None,
    ollama_url: str = "",
) -> tuple[list[Page], int]:
    """Parse a PDF file into pages.

    Returns (pages, low_confidence_count) where pages is a list of
    (text, page_number, ocr_quality) tuples.  Pages with sparse or
    garbled native text are sent through vision OCR.
    """
    reader = PdfReader(file_path)
    pages: list[Page] = []
    low_confidence_count = 0

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if len(text.strip()) >= _OCR_THRESHOLD and not _is_garbled(text):
            pages.append((text, page_num, "native"))
        else:
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
                        ocr_text, confidence = await ocr_page(
                            tmp_path,
                            vision_client=vision_client,
                            vision_model=vision_model,
                            ollama_url=ollama_url,
                        )
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


def load_docx(file_path: str) -> list[Page]:
    """Parse a DOCX file and return a single page."""
    text = docx2txt.process(file_path)
    return [(text, 0, "native")]


def load_xlsx(file_path: str) -> list[Page]:
    """Parse an XLSX file and return one page per worksheet."""
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    try:
        pages: list[Page] = []
        for sheet_idx, sheet in enumerate(wb.worksheets, start=1):
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                row_str = "\t".join(str(cell) if cell is not None else "" for cell in row)
                if row_str.strip():
                    rows.append(row_str)
            pages.append(("\n".join(rows), sheet_idx, "native"))
        return pages
    finally:
        wb.close()
