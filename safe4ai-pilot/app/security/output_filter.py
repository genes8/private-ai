"""Output filter: verify LLM answers before returning them to the caller."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog

from app.models import GuardResult, RankedChunk
from app.security.content_filter import PII_PATTERNS

logger = structlog.get_logger(__name__)

_LONG_ANSWER_THRESHOLD = 4000

# Rule 2 — inference labeling guard.
# If the answer uses general-inference / model-knowledge language, it must
# carry a clear disclaimer that the information is not stated in the documents.
# Limitations:
# - Labeling only: does NOT verify factuality and cannot catch a fabricated
#   entity-specific fact stated with no marker at all.
# - English-only markers, while the rag_answer v2 prompt asks the model to
#   reply in the user's language. Non-English answers fail open (no marker
#   matches, guard passes); a mixed-language answer using an English inference
#   phrase with a localized disclaimer is falsely blocked. Accepted trade-off
#   until a language-aware check exists.
# The disclaimer phrasing is a contract with app.prompts.templates
# INFERENCE_DISCLAIMER — pinned by tests/test_security_guards.py.
_INFERENCE_MARKERS = (
    "general knowledge",
    "general inference",
    "general model knowledge",
    "general world knowledge",
    "model knowledge",
    "common knowledge",
)
_DISCLAIMER_MARKERS = (
    "not stated directly in the documents",
    "not stated in the documents",
    "not confirmed in the documents",
    "documents do not state",
    "not found in the documents",
)


def _find_pii_matches(text: str) -> list[str]:
    """Return all PII substrings found in *text*."""
    matches: list[str] = []
    for pattern in PII_PATTERNS:
        matches.extend(m.group() for m in pattern.finditer(text))
    return matches


class OutputFilter:
    def check(
        self,
        answer: str,
        source_chunks: Sequence[RankedChunk],
        citations: list[Any] | None = None,
    ) -> GuardResult:
        """Check the generated answer before returning it to the caller.

        Rules (evaluated in order):
        0. If source chunks are present but the answer has no citations,
           block the response. This is a state-level check — the graph
           populates citations directly from the retrieved chunks, so an
           empty citation list with non-empty source_chunks indicates a
           code path that skipped citation population.
        1. If the answer contains PII that is absent from every source chunk,
           block the response.
        2. If the answer uses general-inference / model-knowledge language but
           lacks a clear "not in the documents" disclaimer, block the response.
        3. If the answer exceeds 4 000 chars, log a warning (still allowed).
        """
        # Rule 0: Citation presence check
        # Only applies when source documents were retrieved. No-context
        # fallback answers (source_chunks=[]) are exempt.
        if source_chunks and not citations:
            return GuardResult(
                allowed=False,
                reason="Answer cites no sources",
            )

        # Rule 1: PII hallucination check
        answer_pii = _find_pii_matches(answer)
        if answer_pii:
            source_text = " ".join(c.content for c in source_chunks)
            for pii_value in answer_pii:
                if pii_value not in source_text:
                    return GuardResult(
                        allowed=False,
                        reason="Output contains PII not in source documents",
                    )

        # Rule 2: Inference labeling check
        # When the answer uses general-inference / model-knowledge language but
        # carries no "not in the documents" disclaimer, block it. Only enforced
        # when inference language is present — grounded answers are unaffected.
        lowered = answer.lower()
        if any(m in lowered for m in _INFERENCE_MARKERS) and not any(
            m in lowered for m in _DISCLAIMER_MARKERS
        ):
            return GuardResult(
                allowed=False,
                reason="Inference answer missing required disclaimer",
            )

        # Rule 3: Suspicious length heuristic
        if len(answer) > _LONG_ANSWER_THRESHOLD:
            logger.warning(
                "output_suspiciously_long",
                answer_length=len(answer),
                source_chunks=len(source_chunks),
            )

        return GuardResult(allowed=True, reason="ok")
