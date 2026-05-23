"""Input guard: sanitise and validate user queries before they reach the LLM."""

from __future__ import annotations

import html
import re
import unicodedata

from app.models import GuardResult

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(?:^|[.!?]\s+|\bplease\s+)ignore\s+(?:previous|all|prior)\s+instructions",
        r"(?:^|[.!?]\s+)you\s+are\s+now\s+(?:a|an|acting|playing|going\s+to)",
        r"(?:^|[.!?]\s+|\bplease\s+)act\s+as\s+(?:if\s+you\s+are|a|an)\b",
        r"(?:^|[.!?]\s+|\bplease\s+)disregard\s+(?:your|all|the)\s+(?:previous|prior|above|instructions|guidelines|rules|training)",
        r"(?:^|[.!?]\s+)(?:reveal|print|output|show)\s+(?:your\s+)?system\s+prompt",
        r"<\|.*?\|>",  # special tokens
    ]
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


class InputGuard:
    MAX_CHARS = 2048  # ~512 tokens at 4 chars/token

    def check(self, query: str) -> GuardResult:
        # 1. Decode HTML entities, normalize Unicode homoglyphs (NFKC), strip HTML tags
        decoded = html.unescape(query)
        normalized = unicodedata.normalize("NFKC", decoded)
        cleaned = _HTML_TAG_RE.sub("", normalized)
        # Strip non-printable control characters, collapse whitespace
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in " \t\n\r\f\v")
        cleaned = " ".join(cleaned.split())

        # 2. Length check
        if len(cleaned) > self.MAX_CHARS:
            return GuardResult(allowed=False, reason="Query too long")

        # 3. Injection pattern check
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(cleaned):
                return GuardResult(allowed=False, reason="Potential prompt injection detected")

        return GuardResult(allowed=True, reason="ok")
