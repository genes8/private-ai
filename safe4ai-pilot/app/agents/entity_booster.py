from __future__ import annotations

import re

from app.models import RankedChunk

# Query signals that indicate a URL/link lookup intent
_URL_QUERY_RE = re.compile(
    r'\b(url|link|website|site|domain|webpage|web\s*address|http|www\.)\b',
    re.IGNORECASE,
)

# Query signals that indicate an email/contact lookup intent
_EMAIL_QUERY_RE = re.compile(
    r'\b(email|e-mail|contact|reach\s*(out|them|us))\b',
    re.IGNORECASE,
)

# URL pattern in chunk content
_URL_CONTENT_RE = re.compile(r'https?://\S+|www\.\S+')

# Email pattern in chunk content
_EMAIL_CONTENT_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.\w{2,}\b')

# Words that carry no entity-specific meaning — stripped before context extraction
_STOP_WORDS: frozenset[str] = frozenset({
    'a', 'an', 'the', 'is', 'are', 'was', 'what', 'where', 'how', 'do', 'does',
    'have', 'has', 'can', 'you', 'i', 'me', 'us', 'their', 'your', 'my', 'its',
    'for', 'of', 'in', 'on', 'at', 'to', 'by', 'get', 'give', 'find', 'tell',
    'know', 'please', 'any', 'some', 'this', 'that', 'it', 'be', 'with', 'about',
    'also', 'and', 'or', 'not', 'no', 'am', 'if', 'so', 'up',
    # Pronouns — carry no entity-specific meaning; referent resolved via conversation context
    'he', 'she', 'they', 'them', 'him', 'her', 'his', 'hers', 'we', 'our', 'ours',
    'who', 'whom', 'which', 'these', 'those',
})


def _context_tokens(query: str) -> frozenset[str]:
    """Return meaningful tokens from *query* after removing entity-type signal words.

    These tokens represent what the user is asking *about* (the subject entity),
    not the fact type they want (URL / email). Used to verify a chunk is topically
    relevant before applying the entity boost.
    """
    cleaned = _URL_QUERY_RE.sub(' ', query)
    cleaned = _EMAIL_QUERY_RE.sub(' ', cleaned)
    tokens: set[str] = set()
    for tok in re.split(r'\W+', cleaned.lower()):
        # Keep length >= 2 to capture 2-char acronyms (UK, AI, EU) that are valid entity names.
        if len(tok) >= 2 and tok not in _STOP_WORDS:
            tokens.add(tok)
    return frozenset(tokens)


def _chunk_matches_context(content: str, ctx: frozenset[str]) -> bool:
    """Return True when *content* references the entity described by *ctx*.

    Uses word-boundary matching to prevent 2-char acronyms (uk, ai, eu) from
    matching inside ordinary words like "mail", "available", or "trunk".

    Short tokens (len == 2): ALL must match as whole words in the plain-text
    portion of the chunk (AND semantics — prevents any single acronym from
    triggering the boost on unrelated content).

    Long tokens (len > 2): at least ONE must match as a whole word in plain text,
    OR appear as a substring inside a URL/email domain segment (handles entity
    names embedded in domain strings, e.g. "alliance" in "businessaialliance.org").

    When *ctx* is empty the query carried no identifiable entity; the boost is
    skipped — the query rewriter must expand vague pronoun references first.
    """
    if not ctx:
        return False
    content_lower = content.lower()

    # Strip URLs and emails to get plain prose for word-boundary matching.
    text_only = _URL_CONTENT_RE.sub(" ", content_lower)
    text_only = _EMAIL_CONTENT_RE.sub(" ", text_only)

    # Collect tokens from URL/email segments for long-token substring fallback.
    url_email_tokens: frozenset[str] = frozenset(
        t for t in re.split(r"[^a-z0-9]+", content_lower) if t
    )

    short_toks = frozenset(t for t in ctx if len(t) == 2)
    long_toks = frozenset(t for t in ctx if len(t) > 2)

    # ALL short tokens must appear as whole words in plain text.
    for tok in short_toks:
        if not re.search(r"\b" + re.escape(tok) + r"\b", text_only):
            return False

    # At least one long token must appear as a whole word in plain text
    # or as a substring of a URL/email segment.
    if long_toks:
        def _long_matches(tok: str) -> bool:
            if re.search(r"\b" + re.escape(tok) + r"\b", text_only):
                return True
            return any(tok in seg for seg in url_email_tokens)

        if not any(_long_matches(t) for t in long_toks):
            return False

    return True


def boost_entity_chunks(
    query: str,
    chunks: list[RankedChunk],
    threshold: float,
) -> list[RankedChunk]:
    """Boost chunks containing exact-match entities when the query asks for them.

    Cross-encoders score poorly on fact-extraction queries ("give me the URL") because
    the chunk reads as a social post or prose, not as a Q&A answer. This booster
    applies a minimal passing score so these chunks reach grade_chunks_by_score
    without touching the global threshold for semantic queries.

    The boost is constrained to the requested entity's context: a chunk that contains
    a URL for an unrelated company is not boosted when the query names a specific
    organisation. Context is derived by stripping entity-type signal words from the
    query and requiring at least one remaining meaningful token to appear in the chunk.
    """
    wants_url = bool(_URL_QUERY_RE.search(query))
    wants_email = bool(_EMAIL_QUERY_RE.search(query))

    if not wants_url and not wants_email:
        return chunks

    ctx = _context_tokens(query)
    _PASS_SCORE = threshold + 0.05

    result: list[RankedChunk] = []
    for chunk in chunks:
        if chunk.rerank_score >= threshold:
            result.append(chunk)
            continue
        boosted = False
        if wants_url and _URL_CONTENT_RE.search(chunk.content):
            if _chunk_matches_context(chunk.content, ctx):
                boosted = True
        elif wants_email and _EMAIL_CONTENT_RE.search(chunk.content):
            if _chunk_matches_context(chunk.content, ctx):
                boosted = True
        if boosted:
            result.append(chunk.model_copy(update={"rerank_score": _PASS_SCORE}))
        else:
            result.append(chunk)
    return result
