from __future__ import annotations

from app.agents.entity_booster import boost_entity_chunks
from app.models import RankedChunk

_THRESHOLD = 0.45


def _chunk(content: str, score: float = -11.0) -> RankedChunk:
    return RankedChunk(
        chunk_id="c1",
        doc_id="d1",
        filename="baia.pdf",
        page_number=10,
        content=content,
        score=0.5,
        rerank_score=score,
    )


# ---------------------------------------------------------------------------
# URL entity boost — query must name the entity
# ---------------------------------------------------------------------------


def test_url_chunk_boosted_when_query_names_entity() -> None:
    """LinkedIn-style chunk with URL gets boosted when the query identifies the entity."""
    chunk = _chunk(
        "Find out more about the Alliance here: https://businessaialliance.org "
        "#BusinessAIAlliance #AI"
    )
    result = boost_entity_chunks("do you have the Alliance URL?", [chunk], _THRESHOLD)
    assert result[0].rerank_score > _THRESHOLD


def test_url_chunk_boosted_for_entity_website_query() -> None:
    chunk = _chunk("Visit us at https://example.com for more info.")
    result = boost_entity_chunks("what is the example website link?", [chunk], _THRESHOLD)
    assert result[0].rerank_score > _THRESHOLD


def test_url_chunk_boost_score_is_minimal() -> None:
    """Boost score must be just above threshold, not inflated."""
    chunk = _chunk("See https://example.com")
    result = boost_entity_chunks("give me the example url", [chunk], _THRESHOLD)
    assert _THRESHOLD < result[0].rerank_score < _THRESHOLD + 0.2


def test_no_url_in_chunk_not_boosted_for_url_query() -> None:
    """Chunk without URL does not get boosted even when query asks for URL."""
    chunk = _chunk("The alliance was founded in September 2025.")
    result = boost_entity_chunks("give me the Alliance url", [chunk], _THRESHOLD)
    assert result[0].rerank_score < _THRESHOLD


def test_url_query_does_not_boost_already_passing_chunk() -> None:
    """Chunk already above threshold is not modified."""
    chunk = _chunk("See https://example.com", score=0.9)
    result = boost_entity_chunks("what is the example url", [chunk], _THRESHOLD)
    assert result[0].rerank_score == 0.9


# ---------------------------------------------------------------------------
# Email entity boost — query must name the entity
# ---------------------------------------------------------------------------


def test_email_chunk_boosted_when_query_names_entity() -> None:
    chunk = _chunk("Contact us at info@businessaialliance.org for more details.")
    result = boost_entity_chunks("how do I contact the Alliance?", [chunk], _THRESHOLD)
    assert result[0].rerank_score > _THRESHOLD


def test_email_chunk_not_boosted_for_unrelated_query() -> None:
    """Email in chunk should not be boosted for a semantic topic query."""
    chunk = _chunk("Contact us at info@businessaialliance.org")
    result = boost_entity_chunks("what is the code of conduct?", [chunk], _THRESHOLD)
    assert result[0].rerank_score < _THRESHOLD


# ---------------------------------------------------------------------------
# Out-of-scope protection: non-entity queries unchanged
# ---------------------------------------------------------------------------


def test_semantic_query_no_boost_applied() -> None:
    """Generic semantic query does not trigger entity boost, preserving score_floor."""
    chunk = _chunk("The alliance was launched in September 2025 at the Houses of Parliament.")
    result = boost_entity_chunks("tell me more about the alliance", [chunk], _THRESHOLD)
    assert result[0].rerank_score < _THRESHOLD


def test_out_of_scope_question_stays_below_threshold() -> None:
    """A completely off-topic chunk is not boosted even with URL query words."""
    chunk = _chunk("The weather in London is typically rainy in November.", score=-10.0)
    result = boost_entity_chunks("what is the website url", [chunk], _THRESHOLD)
    # No URL in the chunk content → no boost
    assert result[0].rerank_score < _THRESHOLD


def test_multiple_chunks_only_url_bearing_one_boosted() -> None:
    """In a mixed list, only the URL-containing chunk that matches the entity is boosted."""
    url_chunk = _chunk("More info at https://businessaialliance.org")
    no_url_chunk = _chunk("The alliance advances responsible AI in the UK.", score=-10.0)
    result = boost_entity_chunks("give me the Alliance url", [url_chunk, no_url_chunk], _THRESHOLD)
    assert result[0].rerank_score > _THRESHOLD
    assert result[1].rerank_score < _THRESHOLD


# ---------------------------------------------------------------------------
# Context-constrained boost: unrelated entities must NOT be boosted
# ---------------------------------------------------------------------------


def test_url_boost_ignores_unrelated_entity_url() -> None:
    """A URL from an unrelated company is not boosted when the query names a specific org."""
    chunk = _chunk("For job openings visit https://unrelated-company.com/careers", score=-3.0)
    result = boost_entity_chunks("what is BAIA's website URL?", [chunk], _THRESHOLD)
    # Chunk has a URL but no mention of BAIA — context mismatch → no boost
    assert result[0].rerank_score < _THRESHOLD


def test_url_boost_applies_when_context_matches() -> None:
    """A URL chunk is boosted when the chunk content references the queried entity."""
    chunk = _chunk("Find out more about BAIA here: https://businessaialliance.org", score=-11.0)
    result = boost_entity_chunks("what is BAIA's website URL?", [chunk], _THRESHOLD)
    assert result[0].rerank_score > _THRESHOLD


def test_email_boost_ignores_unrelated_entity_email() -> None:
    """An email from an unrelated org is not boosted when the query names a specific entity."""
    chunk = _chunk("Reach HR at hr@unrelated-corp.com for benefits questions.", score=-2.0)
    result = boost_entity_chunks("what is the BAIA contact email?", [chunk], _THRESHOLD)
    assert result[0].rerank_score < _THRESHOLD


def test_email_boost_applies_when_context_matches() -> None:
    """An email chunk is boosted when its content references the queried organisation."""
    chunk = _chunk("BAIA general enquiries: info@businessaialliance.org", score=-11.0)
    result = boost_entity_chunks("what is the BAIA contact email?", [chunk], _THRESHOLD)
    assert result[0].rerank_score > _THRESHOLD


def test_generic_pronoun_query_does_not_boost() -> None:
    """A query with no identifiable entity (only pronouns/stop words) must not boost.

    The query rewriter is responsible for expanding 'their URL' → 'BAIA URL'
    before this function runs. If the rewriter fails, we must not promote
    arbitrary URL-bearing chunks as relevant.
    """
    chunk = _chunk("Visit us at https://example.com for more info.", score=-5.0)
    result = boost_entity_chunks("do you have their URL?", [chunk], _THRESHOLD)
    assert result[0].rerank_score < _THRESHOLD


# ---------------------------------------------------------------------------
# 2-char acronym context tokens (P1 blind-spot fix)
# ---------------------------------------------------------------------------


def test_short_acronym_forms_context_token_and_boosts_match() -> None:
    """2-char acronyms like 'UK' must be kept as context tokens, not discarded."""
    chunk = _chunk("UK AI Alliance website: https://ukaialliance.org", score=-11.0)
    result = boost_entity_chunks("what is the UK AI website URL?", [chunk], _THRESHOLD)
    # 'uk' and 'ai' are valid 2-char context tokens → chunk content matches → boost
    assert result[0].rerank_score > _THRESHOLD


def test_short_acronym_blocks_unrelated_chunk() -> None:
    """2-char acronym context token correctly blocks an unrelated URL chunk."""
    chunk = _chunk("Visit https://unrelated.com for more information", score=-3.0)
    result = boost_entity_chunks("what is the UK AI website URL?", [chunk], _THRESHOLD)
    # Chunk has no mention of 'uk' or 'ai' → no boost
    assert result[0].rerank_score < _THRESHOLD
