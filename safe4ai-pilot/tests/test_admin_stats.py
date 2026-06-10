"""Admin stats route tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.helpers.admin_routes import (
    make_admin_user as _make_admin_user,
)
from tests.helpers.admin_routes import (
    make_pilot_user as _make_pilot_user,
)
from tests.helpers.admin_routes import (
    make_test_client as _make_test_client,
)
from tests.helpers.admin_routes import (
    mock_db_with_admin as _mock_db_with_admin,
)


class TestStats:
    def test_get_stats_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        # scalar() defaults to None in _mock_db_with_admin → triggers 0/None fallbacks

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_queries"] == 0
        assert body["avg_latency_ms"] is None
        assert body["total_cost_usd"] == 0.0
        assert body["cache_total_hits"] == 0
        assert body["unique_users"] == 0
        from app.main import app
        app.dependency_overrides.clear()

    def test_stats_timeseries_zero_fills_missing_days(self) -> None:
        from datetime import date
        from datetime import timedelta as td

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        today = date.today()
        yesterday = today - td(days=1)
        # First .all() is the audit aggregation, second is the cost aggregation.
        db.query.return_value.filter.return_value.group_by.return_value.all.side_effect = [
            [(today.isoformat(), 4, 2)],
            [(yesterday.isoformat(), 0.05), (today.isoformat(), 0.1)],
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/stats/timeseries?days=3")

        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == 3
        series = body["series"]
        assert len(series) == 3
        assert [p["queries"] for p in series] == [0, 0, 4]
        assert [p["unique_users"] for p in series] == [0, 0, 2]
        assert [p["cost_usd"] for p in series] == [0.0, 0.05, 0.1]
        assert series[-1]["date"] == today.isoformat()
        from app.main import app
        app.dependency_overrides.clear()

    def test_stats_timeseries_rejects_out_of_range_days(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/stats/timeseries?days=365")

        assert resp.status_code == 422
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_stats_requires_admin(self) -> None:
        pilot = _make_pilot_user()
        db = _mock_db_with_admin(pilot)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, pilot)
            resp = client.get("/admin/stats")

        assert resp.status_code == 403
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_stats_counts_distinct_querying_users(self) -> None:
        admin = _make_admin_user()
        db = MagicMock()
        db.get.return_value = admin

        total_queries_q = MagicMock()
        total_queries_q.filter.return_value.scalar.return_value = 12
        avg_latency_q = MagicMock()
        avg_latency_q.filter.return_value.scalar.return_value = 155.5
        total_cost_q = MagicMock()
        total_cost_q.filter.return_value.scalar.return_value = 3.25
        cache_hits_q = MagicMock()
        cache_hits_q.filter.return_value.scalar.return_value = 9
        unique_users_q = MagicMock()
        unique_users_q.filter.return_value.scalar.return_value = 4

        db.query.side_effect = [
            total_queries_q,
            avg_latency_q,
            total_cost_q,
            cache_hits_q,
            unique_users_q,
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/stats?days=7")

        assert resp.status_code == 200
        assert resp.json()["unique_users"] == 4
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_stats_uses_cache_hit_events_for_period_hits(self) -> None:
        admin = _make_admin_user()
        db = MagicMock()
        db.get.return_value = admin

        total_queries_q = MagicMock()
        total_queries_q.filter.return_value.scalar.return_value = 12
        avg_latency_q = MagicMock()
        avg_latency_q.filter.return_value.scalar.return_value = 155.5
        total_cost_q = MagicMock()
        total_cost_q.filter.return_value.scalar.return_value = 3.25
        cache_hits_q = MagicMock()
        cache_hits_q.filter.return_value.scalar.return_value = 9
        unique_users_q = MagicMock()
        unique_users_q.filter.return_value.scalar.return_value = 4

        db.query.side_effect = [
            total_queries_q,
            avg_latency_q,
            total_cost_q,
            cache_hits_q,
            unique_users_q,
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/stats?days=7")

        assert resp.status_code == 200
        query_sql = str(db.query.call_args_list[3][0][0])
        assert "semantic_cache_hits.id" in query_sql
        assert resp.json()["cache_total_hits"] == 9
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Current user info (/me)
# ---------------------------------------------------------------------------


class TestCorpusStats:
    def test_corpus_stats_returns_health_fields(self) -> None:
        """GET /admin/corpus-stats must include failedCount and inProgressCount."""
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        # scalar() returns None by default → falls back to 0 for all counts

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/corpus-stats")

        assert resp.status_code == 200
        body = resp.json()
        assert "docCount" in body
        assert "chunkCount" in body
        assert "failedCount" in body
        assert "inProgressCount" in body
        assert body["failedCount"] == 0
        assert body["inProgressCount"] == 0
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tier / quota enforcement (endpoint-level smoke tests)
# Unit tests for the helpers themselves live in test_quota_service.py.
# ---------------------------------------------------------------------------

