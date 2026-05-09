"""Unit tests for observability.feedback — DB session is mocked."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


class TestFeedbackStore:
    def test_store_feedback_creates_row(self, mock_db: MagicMock) -> None:
        from app.db.models import FeedbackRating, QueryFeedback
        from observability.feedback import FeedbackStore

        store = FeedbackStore(mock_db)
        fid = store.store(
            session_id="sess-abc",
            user_id="user-1",
            trace_id="trace-xyz",
            rating=FeedbackRating.positive,
            comment="Great answer!",
        )

        assert fid is not None
        assert len(fid) == 36  # UUID

        mock_db.add.assert_called_once()
        added: QueryFeedback = mock_db.add.call_args[0][0]
        assert isinstance(added, QueryFeedback)
        assert added.id == fid
        assert added.session_id == "sess-abc"
        assert added.user_id == "user-1"
        assert added.trace_id == "trace-xyz"
        assert added.rating == FeedbackRating.positive
        assert added.comment == "Great answer!"
        mock_db.commit.assert_called_once()

    def test_store_feedback_negative_no_comment(self, mock_db: MagicMock) -> None:
        from app.db.models import FeedbackRating, QueryFeedback
        from observability.feedback import FeedbackStore

        store = FeedbackStore(mock_db)
        store.store(
            session_id="sess-def",
            user_id="user-2",
            trace_id="trace-456",
            rating=FeedbackRating.negative,
        )

        added: QueryFeedback = mock_db.add.call_args[0][0]
        assert added.rating == FeedbackRating.negative
        assert added.comment is None

    def test_store_returns_unique_ids(self, mock_db: MagicMock) -> None:
        from app.db.models import FeedbackRating
        from observability.feedback import FeedbackStore

        store = FeedbackStore(mock_db)
        ids = {store.store("s", "u", f"trace-{i}", FeedbackRating.positive) for i in range(10)}
        assert len(ids) == 10  # all unique

    def test_list_for_admin_returns_list(self, mock_db: MagicMock) -> None:
        from app.db.models import FeedbackRating
        from observability.feedback import FeedbackStore

        now = datetime.now(UTC)

        # Build two mock QueryFeedback rows
        def _make_row(idx: int) -> MagicMock:
            row = MagicMock()
            row.id = f"fid-{idx}"
            row.user_id = f"user-{idx}"
            row.session_id = f"sess-{idx}"
            row.trace_id = f"trace-{idx}"
            row.rating = FeedbackRating.positive
            row.comment = f"comment {idx}"
            row.created_at = now
            return row

        fake_rows = [_make_row(1), _make_row(2)]

        # Mock the chained query: db.query(...).order_by(...).limit(...).all()
        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = fake_rows
        mock_db.query.return_value = mock_query

        store = FeedbackStore(mock_db)
        result = store.list_for_admin(mock_db, limit=100)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "fid-1"
        assert result[0]["user_id"] == "user-1"
        assert result[0]["trace_id"] == "trace-1"
        assert result[0]["rating"] == FeedbackRating.positive
        assert "created_at" in result[0]

    def test_list_for_admin_empty(self, mock_db: MagicMock) -> None:
        from observability.feedback import FeedbackStore

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        store = FeedbackStore(mock_db)
        result = store.list_for_admin(mock_db)

        assert result == []
