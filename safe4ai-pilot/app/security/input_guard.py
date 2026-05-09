"""Input guard: sanitise and validate user queries before they reach the LLM."""

from __future__ import annotations

import re

from app.models import GuardResult

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (?:previous|all|prior) instructions",
        r"you are now",
        r"act as (?:if you are|a|an)",
        r"disregard (?:your|all|the)",
        r"system prompt",
        r"<\|.*?\|>",  # special tokens
    ]
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


class InputGuard:
    MAX_CHARS = 2048  # ~512 tokens at 4 chars/token

    def check(self, query: str) -> GuardResult:
        """Validate and sanitise a user query.

        Steps:
        1. Strip HTML tags and non-printable control characters.
        2. Reject if the cleaned text exceeds MAX_CHARS.
        3. Reject if any injection pattern is found.
        """
        # 1. Strip HTML tags then control chars (keep printable + whitespace)
        cleaned = _HTML_TAG_RE.sub("", query)
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in " \t\n\r\f\v")

        # 2. Length check
        if len(cleaned) > self.MAX_CHARS:
            return GuardResult(allowed=False, reason="Query too long")

        # 3. Injection pattern check
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(cleaned):
                return GuardResult(allowed=False, reason="Potential prompt injection detected")

        return GuardResult(allowed=True, reason="ok")
