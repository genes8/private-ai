"""Deterministic follow-up suggestions for the SSE ``done`` payload.

No extra LLM call: suggestions are templated from the documents the answer
actually cited, so they are cheap, predictable, and never hallucinate a
document that does not exist. Empty when the answer had no citations
(fallback / no-context answers should not invite follow-ups).
"""
from __future__ import annotations

from app.models import Citation

_MAX_SUGGESTIONS = 3


def build_follow_up_suggestions(citations: list[Citation]) -> list[str]:
    """Up to three follow-up prompts derived from the cited documents."""
    if not citations:
        return []
    distinct_files: list[str] = []
    for c in citations:
        if c.filename and c.filename not in distinct_files:
            distinct_files.append(c.filename)
    if not distinct_files:
        return []

    suggestions = [f"What else does {distinct_files[0]} say about this topic?"]
    if len(distinct_files) > 1:
        suggestions.append(f"How does {distinct_files[1]} compare on this point?")
    suggestions.append("Summarize the key points from the cited sections.")
    return suggestions[:_MAX_SUGGESTIONS]
