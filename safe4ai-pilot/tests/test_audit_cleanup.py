"""Unit tests for scripts.audit_cleanup — DB session is mocked."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.execute = MagicMock(return_value=MagicMock(rowcount=5))
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


class TestRunCleanup:
    def test_cleanup_deletes_old_audit_logs(self, mock_db: MagicMock) -> None:
        from scripts.audit_cleanup import run_cleanup

        mock_db.execute.return_value = MagicMock(rowcount=3)
        run_cleanup(mock_db, retention_days=90, cache_retention_days=30)

        # db.execute should have been called (for both audit_logs and semantic_cache deletes)
        assert mock_db.execute.call_count == 2

    def test_cleanup_deletes_old_cache(self, mock_db: MagicMock) -> None:
        from scripts.audit_cleanup import run_cleanup

        audit_result = MagicMock(rowcount=2)
        cache_result = MagicMock(rowcount=7)
        mock_db.execute.side_effect = [audit_result, cache_result]

        result = run_cleanup(mock_db, retention_days=90, cache_retention_days=30)

        assert result["cache_rows_deleted"] == 7
        assert mock_db.execute.call_count == 2

    def test_cleanup_writes_summary_log(self, mock_db: MagicMock) -> None:
        from app.db.models import AuditLog
        from scripts.audit_cleanup import run_cleanup

        audit_result = MagicMock(rowcount=4)
        cache_result = MagicMock(rowcount=1)
        mock_db.execute.side_effect = [audit_result, cache_result]

        run_cleanup(mock_db, retention_days=90, cache_retention_days=30)

        mock_db.add.assert_called_once()
        added: AuditLog = mock_db.add.call_args[0][0]
        assert isinstance(added, AuditLog)
        assert added.action_type == "system_cleanup"
        assert added.response_metadata["audit_rows_deleted"] == 4
        assert added.response_metadata["cache_rows_deleted"] == 1
        mock_db.commit.assert_called_once()

    def test_cleanup_returns_counts(self, mock_db: MagicMock) -> None:
        from scripts.audit_cleanup import run_cleanup

        audit_result = MagicMock(rowcount=10)
        cache_result = MagicMock(rowcount=5)
        mock_db.execute.side_effect = [audit_result, cache_result]

        result = run_cleanup(mock_db, retention_days=90, cache_retention_days=30)

        assert "audit_rows_deleted" in result
        assert "cache_rows_deleted" in result
        assert result["audit_rows_deleted"] == 10
        assert result["cache_rows_deleted"] == 5

    def test_cleanup_zero_deletions(self, mock_db: MagicMock) -> None:
        from scripts.audit_cleanup import run_cleanup

        audit_result = MagicMock(rowcount=0)
        cache_result = MagicMock(rowcount=0)
        mock_db.execute.side_effect = [audit_result, cache_result]

        result = run_cleanup(mock_db, retention_days=1, cache_retention_days=1)

        assert result["audit_rows_deleted"] == 0
        assert result["cache_rows_deleted"] == 0

    def test_cleanup_archives_expired_audit_logs_before_delete(
        self,
        mock_db: MagicMock,
        tmp_path,
    ) -> None:
        from app.db.models import AuditLog
        from scripts.audit_cleanup import run_cleanup

        expired = MagicMock(spec=AuditLog)
        expired.id = "audit-old-1"
        expired.user_id = "user-1"
        expired.session_id = "session-1"
        expired.timestamp = datetime.now(UTC) - timedelta(days=120)
        expired.action_type = "query"
        expired.query_text = "what changed?"
        expired.response_metadata = {"trace": "trace-1"}
        expired.latency_ms = 42
        expired.model_used = "qwen3:latest"
        expired.trace_id = "trace-1"

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            expired
        ]
        mock_db.execute.side_effect = [MagicMock(rowcount=1), MagicMock(rowcount=0)]

        result = run_cleanup(
            mock_db,
            retention_days=90,
            cache_retention_days=30,
            archive_dir=tmp_path,
            archive_secret="archive-secret",
        )

        archives = list(tmp_path.glob("audit-*.jsonl"))
        manifests = list(tmp_path.glob("audit-*.manifest.json"))
        assert len(archives) == 1
        assert len(manifests) == 1
        assert result["audit_rows_archived"] == 1

        archived_row = json.loads(archives[0].read_text().splitlines()[0])
        manifest = json.loads(manifests[0].read_text())
        assert archived_row["id"] == "audit-old-1"
        assert archived_row["action_type"] == "query"
        assert manifest["row_count"] == 1
        assert manifest["final_hash"]
        assert manifest["hmac_sha256"]

        added: AuditLog = mock_db.add.call_args[0][0]
        assert added.response_metadata["archive_rows"] == 1
        assert added.response_metadata["archive_manifest_path"].endswith(".manifest.json")
