"""Content filter: detect and remove PII from retrieved document chunks."""

from __future__ import annotations

import re

import structlog

from app.models import RankedChunk

logger = structlog.get_logger(__name__)

PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{3}[ -]\d{2}[ -]\d{4}\b"),  # SSN: ###-##-#### or ### ## ####
    re.compile(r"\b(?:\d{4}[- ]){3}\d{4}\b"),  # Credit card
    re.compile(r"(?<![A-Z0-9])\b[A-Z]{1,2}\d{7,9}\b(?![A-Z0-9])"),  # Passport (7-9 digits)
]


def _contains_pii(text: str) -> bool:
    return any(p.search(text) for p in PII_PATTERNS)


def _redact_pii(text: str) -> str:
    for pattern in PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class ContentFilter:
    def __init__(self, blocked_terms: list[str] | None = None) -> None:
        self._blocked_terms = [t.lower() for t in (blocked_terms or [])]

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

    def filter_blocked_sections(self, chunks: list[RankedChunk]) -> list[RankedChunk]:
        """Remove chunks whose content matches any configured blocked term."""
        if not self._blocked_terms:
            return chunks
        clean: list[RankedChunk] = []
        for chunk in chunks:
            text_lower = chunk.content.lower()
            matched = next((t for t in self._blocked_terms if t in text_lower), None)
            if matched:
                logger.warning(
                    "blocked_term_chunk_excluded",
                    chunk_id=chunk.chunk_id,
                    term=matched,
                )
            else:
                clean.append(chunk)
        return clean

    def redact(self, text: str) -> str:
        """Replace PII patterns with [REDACTED], preserving surrounding content."""
        return _redact_pii(text)

    def is_pii(self, text: str) -> bool:
        """Return True if the text contains any recognised PII pattern."""
        return _contains_pii(text)
