"""Unit tests for observability.cost_tracker — DB session is mocked."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


class TestCalculateCost:
    def test_calculate_cost_basic(self) -> None:
        from observability.cost_tracker import CostTracker

        tracker = CostTracker(cost_per_1k_tokens=0.002)
        cost = tracker.calculate(prompt_tokens=1000, completion_tokens=1000)
        assert cost == pytest.approx(0.004)

    def test_calculate_zero_cost(self) -> None:
        from observability.cost_tracker import CostTracker

        tracker = CostTracker(cost_per_1k_tokens=0.0)
        cost = tracker.calculate(prompt_tokens=5000, completion_tokens=3000)
        assert cost == 0.0

    def test_calculate_partial_tokens(self) -> None:
        from observability.cost_tracker import CostTracker

        tracker = CostTracker(cost_per_1k_tokens=1.0)
        # 500 total tokens → 500 / 1000 * 1.0 = 0.5
        cost = tracker.calculate(prompt_tokens=250, completion_tokens=250)
        assert cost == pytest.approx(0.5)

    def test_calculate_large_token_count(self) -> None:
        from observability.cost_tracker import CostTracker

        tracker = CostTracker(cost_per_1k_tokens=0.01)
        cost = tracker.calculate(prompt_tokens=100_000, completion_tokens=0)
        assert cost == pytest.approx(1.0)


class TestRecordRun:
    def test_record_run_creates_db_row(self, mock_db: MagicMock) -> None:
        from app.db.models import AgentRun
        from observability.cost_tracker import CostTracker

        tracker = CostTracker(cost_per_1k_tokens=0.002)
        run_id = tracker.record_run(
            db=mock_db,
            session_id="sess-123",
            prompt_tokens=1000,
            completion_tokens=1000,
            model="qwen3.5:9b",
        )

        assert run_id is not None
        assert len(run_id) == 36  # UUID length

        mock_db.add.assert_called_once()
        added_obj: AgentRun = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, AgentRun)
        assert added_obj.id == run_id
        assert added_obj.session_id == "sess-123"
        assert added_obj.cost_usd == pytest.approx(0.004)
        assert added_obj.status == "completed"
        mock_db.commit.assert_called_once()

    def test_record_run_custom_status(self, mock_db: MagicMock) -> None:
        from app.db.models import AgentRun
        from observability.cost_tracker import CostTracker

        tracker = CostTracker(cost_per_1k_tokens=0.002)
        tracker.record_run(
            db=mock_db,
            session_id="sess-456",
            prompt_tokens=100,
            completion_tokens=50,
            model="qwen3.5:9b",
            status="failed",
        )

        added_obj: AgentRun = mock_db.add.call_args[0][0]
        assert added_obj.status == "failed"

    def test_record_run_returns_valid_uuid(self, mock_db: MagicMock) -> None:
        import uuid

        from observability.cost_tracker import CostTracker

        tracker = CostTracker(cost_per_1k_tokens=0.0)
        run_id = tracker.record_run(
            db=mock_db,
            session_id="sess-789",
            prompt_tokens=0,
            completion_tokens=0,
            model="test",
        )
        # Should be parseable as UUID
        uuid.UUID(run_id)


class TestGetStats:
    def test_get_stats_returns_summary_structure(self, mock_db: MagicMock) -> None:
        from observability.cost_tracker import CostTracker

        # First call: aggregate query (.one()) returns total_cost, runs_count
        agg_result = MagicMock()
        agg_result.one.return_value = (0.01, 3)
        # Second call: daily breakdown query iterates rows
        day_result = MagicMock()
        day_result.__iter__ = MagicMock(return_value=iter([
            ("2026-05-01", 0.005, 2),
            ("2026-05-02", 0.005, 1),
        ]))
        mock_db.execute.side_effect = [agg_result, day_result]

        tracker = CostTracker(cost_per_1k_tokens=0.002)
        stats = tracker.get_stats(mock_db, days=30)

        assert "total_cost_usd" in stats
        assert "runs_count" in stats
        assert "by_day" in stats
        assert stats["runs_count"] == 3
        assert stats["total_cost_usd"] == pytest.approx(0.01)
        assert len(stats["by_day"]) == 2

    def test_get_stats_empty_result(self, mock_db: MagicMock) -> None:
        from observability.cost_tracker import CostTracker

        agg_result = MagicMock()
        agg_result.one.return_value = (0.0, 0)
        day_result = MagicMock()
        day_result.__iter__ = MagicMock(return_value=iter([]))
        mock_db.execute.side_effect = [agg_result, day_result]

        tracker = CostTracker(cost_per_1k_tokens=0.002)
        stats = tracker.get_stats(mock_db, days=30)

        assert stats["total_cost_usd"] == 0.0
        assert stats["runs_count"] == 0
        assert stats["by_day"] == []

    def test_get_stats_by_day_sorted(self, mock_db: MagicMock) -> None:
        from observability.cost_tracker import CostTracker

        # SQL GROUP BY + ORDER BY returns sorted results
        agg_result = MagicMock()
        agg_result.one.return_value = (0.006, 2)
        day_result = MagicMock()
        day_result.__iter__ = MagicMock(return_value=iter([
            ("2026-05-01", 0.001, 1),
            ("2026-05-05", 0.005, 1),
        ]))
        mock_db.execute.side_effect = [agg_result, day_result]

        tracker = CostTracker(cost_per_1k_tokens=0.002)
        stats = tracker.get_stats(mock_db, days=30)

        dates = [entry["date"] for entry in stats["by_day"]]
        assert dates == sorted(dates)
