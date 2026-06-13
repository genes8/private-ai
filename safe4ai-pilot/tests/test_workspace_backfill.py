"""Tests for the Qdrant workspace_id payload backfill (`workspace_backfill`).

Verifies the fail-closed readiness contract: a Qdrant outage leaves the flag
unset (so retrieval stays fail-closed and /health degraded), and a later
successful pass tags legacy points, flips the flag, and rebuilds BM25.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.db.models import DEFAULT_WORKSPACE_ID


def _point(point_id: str, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(id=point_id, payload=payload)


def _patch_flag(store: dict) -> tuple:
    """Patch app_config load/upsert against an in-memory dict."""
    load = patch(
        "app.services.workspace_backfill.load_app_config",
        side_effect=lambda _db: dict(store),
    )
    upsert = patch(
        "app.services.workspace_backfill.upsert_app_config",
        side_effect=lambda _db, updates, **_kw: store.update(updates),
    )
    session = patch("app.services.workspace_backfill.SessionLocal")
    return load, upsert, session


def test_backfill_failure_leaves_flag_unset() -> None:
    """A Qdrant outage returns False and never sets the completion flag."""
    from app.services import workspace_backfill

    store: dict = {}
    load, upsert, session = _patch_flag(store)
    client = MagicMock()
    client.collection_exists.side_effect = ConnectionError("qdrant down")

    with load, upsert, session, patch(
        "app.services.workspace_backfill.QdrantClient", return_value=client
    ):
        result = workspace_backfill.backfill_qdrant_workspace_payload(retriever=None)

    assert result is False
    assert workspace_backfill.BACKFILL_FLAG not in store


def test_backfill_tags_legacy_points_sets_flag_and_rebuilds_bm25() -> None:
    """A successful pass tags only untagged points, flips the flag, rebuilds BM25."""
    from app.services import workspace_backfill

    store: dict = {}
    load, upsert, session = _patch_flag(store)

    client = MagicMock()
    client.collection_exists.return_value = True
    # One legacy point (no workspace_id) and one already-tagged point.
    client.scroll.return_value = (
        [
            _point("legacy-1", {"content": "x"}),
            _point("tagged-1", {"content": "y", "workspace_id": "ws-other"}),
        ],
        None,  # no further pages
    )
    retriever = MagicMock()

    with load, upsert, session, patch(
        "app.services.workspace_backfill.QdrantClient", return_value=client
    ):
        result = workspace_backfill.backfill_qdrant_workspace_payload(retriever=retriever)

    assert result is True
    assert store[workspace_backfill.BACKFILL_FLAG] is True
    # Only the untagged point is rewritten, to the default workspace.
    client.set_payload.assert_called_once()
    _, kwargs = client.set_payload.call_args
    assert kwargs["payload"] == {"workspace_id": DEFAULT_WORKSPACE_ID}
    assert kwargs["points"] == ["legacy-1"]
    # BM25 rebuilt so the sparse path carries workspace_id too.
    retriever.rebuild_from_qdrant.assert_called_once()


def test_backfill_noop_when_already_complete() -> None:
    """If the flag is already set, the backfill short-circuits without scrolling."""
    from app.services import workspace_backfill

    store = {workspace_backfill.BACKFILL_FLAG: True}
    load, upsert, session = _patch_flag(store)
    client = MagicMock()

    with load, upsert, session, patch(
        "app.services.workspace_backfill.QdrantClient", return_value=client
    ):
        result = workspace_backfill.backfill_qdrant_workspace_payload(retriever=None)

    assert result is True
    client.scroll.assert_not_called()
