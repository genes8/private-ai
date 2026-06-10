"""Admin audit log route tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from tests.helpers.admin_routes import (
    make_admin_user as _make_admin_user,
)
from tests.helpers.admin_routes import (
    make_test_client as _make_test_client,
)
from tests.helpers.admin_routes import (
    mock_db_with_admin as _mock_db_with_admin,
)


class TestAuditLogs:
    def test_list_audit_logs_returns_200(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        _paged = db.query.return_value.order_by.return_value.offset.return_value.limit.return_value
        _paged.all.return_value = []

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs")

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        from app.main import app
        app.dependency_overrides.clear()

    def test_list_audit_logs_returns_user_email_for_display(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        audit = MagicMock()
        audit.id = "audit-1"
        audit.user_id = "user-1"
        audit.session_id = "sess-1"
        audit.timestamp = datetime.now(UTC)
        audit.action_type = "settings_provider_change"
        audit.query_text = None
        audit.latency_ms = None
        audit.model_used = None
        audit.trace_id = "trace-1"

        _paged = (
            db.query.return_value.outerjoin.return_value.order_by.return_value.offset.return_value
            .limit.return_value
        )
        _paged.all.return_value = [(audit, "pilot@example.com")]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs")

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["user_email"] == "pilot@example.com"
        assert body[0]["user_id"] == "user-1"
        from app.main import app
        app.dependency_overrides.clear()

    def test_list_audit_logs_includes_kind(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        audit = MagicMock()
        audit.id = "audit-1"
        audit.user_id = "user-1"
        audit.session_id = "sess-1"
        audit.timestamp = datetime.now(UTC)
        audit.action_type = "chat_query"
        audit.query_text = "q"
        audit.latency_ms = 10
        audit.model_used = None
        audit.trace_id = None

        _joined = db.query.return_value.outerjoin.return_value.order_by.return_value
        _joined.offset.return_value.limit.return_value.all.return_value = [
            (audit, "pilot@example.com")
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs")

        assert resp.status_code == 200
        assert resp.json()[0]["kind"] == "query"
        from app.main import app
        app.dependency_overrides.clear()

    def test_list_audit_logs_rejects_unknown_kind(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs?kind=bogus")

        assert resp.status_code == 422
        from app.main import app
        app.dependency_overrides.clear()

    def test_list_audit_logs_kind_filter_uses_server_side_in_clause(self) -> None:
        """kind=query must resolve to the matching action types and filter in SQL."""
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        audit = MagicMock()
        audit.id = "audit-1"
        audit.user_id = "user-1"
        audit.session_id = "sess-1"
        audit.timestamp = datetime.now(UTC)
        audit.action_type = "chat_query"
        audit.query_text = "q"
        audit.latency_ms = 10
        audit.model_used = None
        audit.trace_id = None

        # distinct() chain feeds the kind→action_type resolution
        db.query.return_value.distinct.return_value.all.return_value = [
            ("chat_query",),
            ("settings_provider_change",),
        ]
        _joined = db.query.return_value.outerjoin.return_value.order_by.return_value
        _joined.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            (audit, "pilot@example.com")
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs?kind=query")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["kind"] == "query"
        from app.main import app
        app.dependency_overrides.clear()

    def test_list_audit_logs_kind_filter_no_matching_types_returns_empty(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.distinct.return_value.all.return_value = [
            ("settings_provider_change",),
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs?kind=fallback")

        assert resp.status_code == 200
        assert resp.json() == []
        from app.main import app
        app.dependency_overrides.clear()

    def test_audit_kind_counts_aggregates_by_kind(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.group_by.return_value.all.return_value = [
            ("chat_query", 5),
            ("settings_provider_change", 2),
            ("user_created", 1),
            ("mystery_event", 3),
        ]

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs/kind-counts")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 11
        assert body["kinds"]["query"] == 5
        assert body["kinds"]["admin"] == 3
        assert body["kinds"]["other"] == 3
        assert body["kinds"]["upload"] == 0
        from app.main import app
        app.dependency_overrides.clear()

    def test_export_csv_returns_csv(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.order_by.return_value.all.return_value = []

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.get("/admin/audit-logs/export.csv")

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------
