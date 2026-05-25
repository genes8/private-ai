"""Output filter: verify LLM answers before returning them to the caller."""

from __future__ import annotations

import structlog

from app.models import GuardResult, RankedChunk
from app.security.content_filter import PII_PATTERNS

logger = structlog.get_logger(__name__)

_LONG_ANSWER_THRESHOLD = 4000


def _find_pii_matches(text: str) -> list[str]:
    """Return all PII substrings found in *text*."""
    matches: list[str] = []
    for pattern in PII_PATTERNS:
        matches.extend(m.group() for m in pattern.finditer(text))
    return matches


class OutputFilter:
    def check(self, answer: str, source_chunks: list[RankedChunk]) -> GuardResult:
        """Check the generated answer for PII hallucination and suspicious length.

        Rules:
        1. If the answer contains PII that is absent from every source chunk,
           block the response.
        2. If the answer exceeds 4 000 chars, log a warning (still allowed).
        """
        # 1. PII hallucination check
        answer_pii = _find_pii_matches(answer)
        if answer_pii:
            source_text = " ".join(c.content for c in source_chunks)
            for pii_value in answer_pii:
                if pii_value not in source_text:
                    return GuardResult(
                        allowed=False,
                        reason="Output contains PII not in source documents",
                    )

        # 2. Suspicious length heuristic
        if len(answer) > _LONG_ANSWER_THRESHOLD:
            logger.warning(
                "output_suspiciously_long",
                answer_length=len(answer),
                source_chunks=len(source_chunks),
            )

        return GuardResult(allowed=True, reason="ok")
