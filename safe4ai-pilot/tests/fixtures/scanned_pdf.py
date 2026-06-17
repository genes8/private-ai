"""Generate an image-only ("scanned") PDF that forces the OCR ingestion path.

The RAG ingester routes a PDF page to the vision/OCR model when native text
extraction yields too few characters (``_OCR_THRESHOLD`` in
``app/services/document_parser.py``). A PDF built from rasterized text images has
no extractable text layer, so every page takes the OCR path — exactly what the
OCR smoke test needs to exercise.

We generate this at test time with Pillow (already a dependency) rather than
committing a binary blob, so the fixture stays reproducible and reviewable.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Text rendered as pixels (no selectable text layer) so ingestion must OCR it.
_PAGE_LINES = (
    "SAFE4AI OCR SMOKE FIXTURE",
    "",
    "Invoice number: SF-2026-0613",
    "Vendor: Northwind Analytics Ltd",
    "Total due: 4,210.00 GBP",
    "Net terms: 30 days from receipt",
    "",
    "This page is a rasterized image with no embedded text layer,",
    "so document ingestion must use the vision OCR path to read it.",
)


def _render_page(width: int = 1240, height: int = 1754) -> Image.Image:
    """Render the fixture text as a single white A4-ish page image."""
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=44)
    except TypeError:
        font = ImageFont.load_default()
    y = 120
    for line in _PAGE_LINES:
        draw.text((110, y), line, fill="black", font=font)
        y += 90
    return image


def write_scanned_pdf(path: Path, *, pages: int = 1, dpi: float = 150.0) -> Path:
    """Write an image-only PDF to ``path`` and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    page = _render_page()
    extras = [page for _ in range(max(0, pages - 1))]
    page.save(path, "PDF", resolution=dpi, save_all=True, append_images=extras)
    return path
