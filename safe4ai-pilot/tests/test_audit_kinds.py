"""Unit tests for the canonical audit kind classifier."""
from __future__ import annotations

import pytest

from app.audit.kinds import AUDIT_KINDS, classify_action_type


@pytest.mark.parametrize(
    ("action_type", "expected"),
    [
        ("chat_query", "query"),
        ("query", "query"),
        ("upload", "upload"),
        ("document_delete", "upload"),
        ("ingest_start", "upload"),
        ("reindex", "upload"),
        ("feedback", "feedback"),
        ("feedback_submitted", "feedback"),
        ("login", "login"),
        ("logout", "login"),
        ("auth_lockout", "login"),
        ("fallback", "fallback"),
        ("settings_provider_change", "admin"),
        ("user_created", "admin"),
        ("admin_export", "admin"),
        ("review_approved", "admin"),
        ("something_unmapped", "other"),
        ("", "other"),
    ],
)
def test_classify_action_type(action_type: str, expected: str) -> None:
    assert classify_action_type(action_type) == expected


def test_every_classification_is_a_known_kind() -> None:
    """The classifier may never invent a kind the API/UI doesn't know."""
    samples = ["chat_query", "upload_x", "feedback_y", "login_z", "fallback", "settings", "junk"]
    for s in samples:
        assert classify_action_type(s) in AUDIT_KINDS
