"""Unit tests for deterministic follow-up suggestions."""
from __future__ import annotations

from app.models import Citation
from app.services.follow_ups import build_follow_up_suggestions


def _cite(filename: str) -> Citation:
    return Citation(filename=filename, page_number=1, excerpt="x", score=0.9)


def test_no_citations_means_no_suggestions() -> None:
    assert build_follow_up_suggestions([]) == []


def test_single_document_yields_two_suggestions() -> None:
    out = build_follow_up_suggestions([_cite("policy.pdf"), _cite("policy.pdf")])
    assert len(out) == 2
    assert "policy.pdf" in out[0]
    assert out[1] == "Summarize the key points from the cited sections."


def test_two_documents_yield_three_suggestions() -> None:
    out = build_follow_up_suggestions([_cite("a.pdf"), _cite("b.docx"), _cite("a.pdf")])
    assert len(out) == 3
    assert "a.pdf" in out[0]
    assert "b.docx" in out[1]


def test_suggestions_are_deterministic() -> None:
    cites = [_cite("a.pdf"), _cite("b.docx")]
    assert build_follow_up_suggestions(cites) == build_follow_up_suggestions(cites)
