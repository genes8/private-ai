"""Tests for the workspace schema migration (`_ensure_workspace_schema`).

Two layers:

* a fast mock-engine test that pins the emitted DDL/backfill SQL (runs in the
  default unit suite, no Docker);
* a real-Postgres test that seeds a *legacy* (pre-workspace) database, runs the
  migration, and asserts the backfill + idempotency end to end.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

from app.db.models import DEFAULT_WORKSPACE_ID, DELETED_USER_ID


def test_workspace_migration_emits_schema_backfill_and_constraints() -> None:
    from app.startup_migrations import _ensure_workspace_schema

    executed: list[str] = []
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = lambda *args, **kwargs: executed.append(str(args[0]))
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    with patch("app.startup_migrations.engine", mock_engine):
        _ensure_workspace_schema()

    sql = "\n".join(executed)
    # Tables
    assert "CREATE TABLE IF NOT EXISTS workspaces" in sql
    assert "CREATE TABLE IF NOT EXISTS workspace_memberships" in sql
    # workspace_id added to (and backfilled on) every scoped table
    scoped_tables = (
        "documents",
        "sessions",
        "audit_logs",
        "semantic_cache",
        "agent_runs",
        "query_feedback",
        "human_review_queue",
    )
    for table in scoped_tables:
        assert ("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS workspace_id") in sql
    # One backfill UPDATE per scoped table.
    assert sql.count("SET workspace_id = :ws WHERE workspace_id IS NULL") == len(scoped_tables)
    # Default workspace + membership backfill
    assert "INSERT INTO workspaces" in sql
    assert "INSERT INTO workspace_memberships" in sql
    assert "workspace_admin" in sql  # admins become workspace_admins
    # Constraints tightened on the load-bearing tables
    assert "documents_workspace_id_fkey" in sql
    assert "ON DELETE RESTRICT" in sql
    assert "ALTER TABLE documents ALTER COLUMN workspace_id SET NOT NULL" in sql


def test_workspace_membership_backfill_casts_role_to_workspacerole_enum() -> None:
    # Regression guard: Postgres rejects CASE ... END (text) for the workspacerole
    # enum column in prod with DatatypeMismatch; the integration test does not
    # reproduce it, so pin the ::workspacerole cast in the emitted SQL.
    from app.startup_migrations import _ensure_workspace_schema

    executed: list[str] = []
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = lambda *args, **kwargs: executed.append(str(args[0]))
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    with patch("app.startup_migrations.engine", mock_engine):
        _ensure_workspace_schema()

    membership_sql = next(s for s in executed if "INSERT INTO workspace_memberships" in s)
    assert "END)::workspacerole" in membership_sql.replace("\n", " ").replace("  ", " ")


# ---------------------------------------------------------------------------
# Real-Postgres backfill + idempotency
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_workspace_migration_backfills_legacy_db_and_is_idempotent(pg_container: str) -> None:
    """Seed a pre-workspace DB, run the migration twice, assert backfill + idempotency."""
    engine = create_engine(pg_container)

    # 1. Build the *current* schema, then strip the workspace bits to emulate a
    #    legacy deployment that predates this migration.
    from app.db import Base

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS workspace_memberships CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS workspaces CASCADE"))
        for table in ("documents", "sessions", "audit_logs", "semantic_cache"):
            conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS workspace_id"))

    # 2. Seed legacy rows: the sentinel user, an admin, a member, and a document.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role, is_active) "
                "VALUES (:id, :email, 'x', 'pilot_user', false)"
            ),
            {"id": DELETED_USER_ID, "email": "deleted@redacted.local"},
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role, is_active) VALUES "
                "('admin-1', 'admin@x.local', 'x', 'admin', true), "
                "('member-1', 'member@x.local', 'x', 'pilot_user', true)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents (id, filename, storage_filename, file_type, "
                "ingestion_status, uploaded_by) "
                "VALUES ('doc-1', 'f.pdf', 's.pdf', 'PDF', 'indexed', 'admin-1')"
            )
        )

    # 3. Run the migration twice against this engine.
    test_engine = create_engine(pg_container)
    with patch("app.startup_migrations.engine", test_engine):
        from app.startup_migrations import _ensure_workspace_schema

        _ensure_workspace_schema()
        _ensure_workspace_schema()  # idempotent second pass

    # 4. Assert backfill + idempotency.
    with engine.begin() as conn:
        ws = conn.execute(
            text("SELECT name, slug FROM workspaces WHERE id = :id"),
            {"id": DEFAULT_WORKSPACE_ID},
        ).one()
        assert ws == ("General", "general")

        doc_ws = conn.execute(
            text("SELECT workspace_id FROM documents WHERE id = 'doc-1'")
        ).scalar_one()
        assert doc_ws == DEFAULT_WORKSPACE_ID

        # Active users are members; the sentinel user is excluded.
        members = dict(
            conn.execute(
                text("SELECT user_id, role FROM workspace_memberships WHERE workspace_id = :id"),
                {"id": DEFAULT_WORKSPACE_ID},
            ).all()
        )
        assert members == {"admin-1": "workspace_admin", "member-1": "member"}
        assert DELETED_USER_ID not in members

        # Idempotency: exactly one membership row per user, one default workspace.
        ws_count = conn.execute(
            text("SELECT count(*) FROM workspaces WHERE id = :id"), {"id": DEFAULT_WORKSPACE_ID}
        ).scalar_one()
        assert ws_count == 1
        membership_count = conn.execute(
            text("SELECT count(*) FROM workspace_memberships")
        ).scalar_one()
        assert membership_count == 2

        # The NOT NULL + FK constraint is now in place.
        not_null = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'documents' AND column_name = 'workspace_id'"
            )
        ).scalar_one()
        assert not_null == "NO"
