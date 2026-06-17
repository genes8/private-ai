"""Canonical audit kind taxonomy.

The admin UI groups raw ``action_type`` values into a small set of kinds.
This classifier is the single source of truth for that grouping: the
``/admin/audit-logs`` kind filter and the kind-count endpoint both derive
their SQL from it, so sidebar counts always match the filtered list.
"""
from __future__ import annotations

AUDIT_KINDS: tuple[str, ...] = (
    "query",
    "upload",
    "feedback",
    "login",
    "fallback",
    "admin",
    "other",
)


def classify_action_type(action_type: str) -> str:
    """Map a raw ``action_type`` value to its UI kind."""
    t = action_type.strip().lower()
    if t in {"chat_query", "query"}:
        return "query"
    if t.startswith(("upload", "document", "ingest", "reindex")):
        return "upload"
    if t.startswith("feedback"):
        return "feedback"
    if t.startswith(("login", "logout", "auth", "saml")):
        return "login"
    if t.startswith("fallback"):
        return "fallback"
    if t.startswith(("settings", "user", "admin", "provider", "review", "workspace")):
        return "admin"
    return "other"
