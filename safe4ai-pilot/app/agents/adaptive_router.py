from __future__ import annotations

from app.models import PrivateAIState


def route_after_grade(state: PrivateAIState) -> str:
    """Synchronous fallback rule: ≥ 2 relevant chunks → generate, else → decompose."""
    if sum(1 for c in state.graded_chunks if c.relevant) >= 2:
        return "generate"
    return "decompose"


def route_quality_gate(state: PrivateAIState) -> str:
    """Synchronous rule: grounded answer → respond, otherwise → fallback."""
    if state.grounded:
        return "respond"
    return "fallback"
