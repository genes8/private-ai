"""Content filter: detect and remove PII from retrieved document chunks."""

from __future__ import annotations

import re

import structlog

from app.models import RankedChunk

logger = structlog.get_logger(__name__)

PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b(?:\d{4}[- ]){3}\d{4}\b"),  # Credit card
    re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),  # Passport
]


def _contains_pii(text: str) -> bool:
    return any(p.search(text) for p in PII_PATTERNS)


class ContentFilter:
    def filter_chunks(self, chunks: list[RankedChunk]) -> list[RankedChunk]:
        """Remove chunks whose content contains PII, logging each exclusion."""
        clean: list[RankedChunk] = []
        for chunk in chunks:
            if _contains_pii(chunk.content):
                logger.warning(
                    "pii_chunk_excluded",
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                )
            else:
                clean.append(chunk)
        return clean

    def is_pii(self, text: str) -> bool:
        """Return True if the text contains any recognised PII pattern."""
        return _contains_pii(text)
