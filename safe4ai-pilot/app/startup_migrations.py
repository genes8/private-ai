"""Boot-time schema fixes and sanity checks.

Additive DDL statements and data validations that run on every startup to
handle rolling schema upgrades without a full Alembic migration file.
Separate from main.py so app composition stays free of schema repair logic.
"""
from __future__ import annotations

import os
from secrets import token_urlsafe

import structlog
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, engine
from app.db.models import DEFAULT_WORKSPACE_ID, DELETED_USER_ID

logger = structlog.get_logger(__name__)

_QDRANT_COLLECTION = "documents"
_QDRANT_VECTOR_SIZE = 768
_DELETED_USER_ID = DELETED_USER_ID  # alias kept so call-sites below are unchanged
_DEFAULT_WORKSPACE_ID = DEFAULT_WORKSPACE_ID
_DELETED_USER_EMAIL = "deleted@redacted.local"


def run_startup_migrations() -> None:
    """Run all boot-time schema fixes and sanity checks in order."""
    _ensure_documents_columns()
    _ensure_document_version_schema()
    _ensure_user_columns()
    _ensure_document_foreign_keys()
    _ensure_agentrun_fk()
    _ensure_deleted_user()
    # Must run AFTER _ensure_deleted_user(): the default workspace's created_by
    # references the sentinel user, which must exist first.
    _ensure_workspace_schema()
    _ensure_tier_config()
    _ensure_qdrant_collection()
    _ensure_semantic_cache_dimension()
    _warn_default_credentials()


def _ensure_documents_columns() -> None:
    statements = [
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size_bytes INTEGER",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS active_version INTEGER DEFAULT 1",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS active_version_id TEXT",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS title TEXT",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pending_version INTEGER",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pending_filename TEXT",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pending_storage_filename TEXT",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pending_file_type TEXT",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS pending_file_size_bytes INTEGER",
    ]
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("document_columns_ensure_failed", error=str(exc))


def _ensure_document_version_schema() -> None:
    # Phase 1: DDL — CREATE TABLE, ALTER TABLE, CREATE INDEX
    # Run these first and in their own transaction so schema changes survive
    # even if the data migration below hits an issue.
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL,
            filename TEXT NOT NULL,
            storage_filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size_bytes INTEGER,
            checksum TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001'
                REFERENCES users(id) ON DELETE SET DEFAULT,
            created_at TIMESTAMPTZ DEFAULT now(),
            ingestion_started_at TIMESTAMPTZ,
            ingested_at TIMESTAMPTZ,
            activated_at TIMESTAMPTZ,
            failed_at TIMESTAMPTZ,
            failed_reason TEXT,
            CONSTRAINT uq_document_versions_document_id_version_number
                UNIQUE (document_id, version_number)
        )
        """,
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS document_version_id TEXT",
        "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS document_version_id TEXT",
        (
            "CREATE INDEX IF NOT EXISTS ix_document_versions_document_id "
            "ON document_versions(document_id)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_document_version_id "
            "ON document_chunks(document_version_id)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_document_version_id "
            "ON ingestion_jobs(document_version_id)"
        ),
    ]
    try:
        with engine.begin() as conn:
            for statement in ddl_statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("document_version_ddl_failed", error=str(exc))
        return

    # Phase 2: Data migration — INSERT/UPDATE
    # Note: Using exec_driver_sql to avoid SQLAlchemy text() parsing `':v'`
    # inside string literals as a bind parameter.
    dml_statements = [
        """
        INSERT INTO document_versions (
            id,
            document_id,
            version_number,
            filename,
            storage_filename,
            file_type,
            file_size_bytes,
            status,
            created_by,
            created_at,
            ingested_at,
            activated_at
        )
        SELECT
            documents.id || '-v' || COALESCE(documents.active_version, documents.version, 1)::text,
            documents.id,
            COALESCE(documents.active_version, documents.version, 1),
            documents.filename,
            documents.storage_filename,
            documents.file_type,
            documents.file_size_bytes,
            'active',
            documents.uploaded_by,
            documents.uploaded_at,
            documents.uploaded_at,
            documents.uploaded_at
        FROM documents
        WHERE NOT EXISTS (
            SELECT 1 FROM document_versions
            WHERE document_versions.document_id = documents.id
        )
        """,
        """
        UPDATE documents
        SET active_version_id = document_versions.id,
            title = COALESCE(documents.title, document_versions.filename)
        FROM document_versions
        WHERE document_versions.document_id = documents.id
          AND document_versions.version_number =
              COALESCE(documents.active_version, documents.version, 1)
          AND documents.active_version_id IS NULL
        """,
        """
        UPDATE document_chunks
        SET document_version_id = document_versions.id
        FROM document_versions
        WHERE document_versions.document_id = document_chunks.document_id
          AND document_versions.version_number = COALESCE(document_chunks.chunk_version, 1)
          AND document_chunks.document_version_id IS NULL
        """,
        """
        UPDATE ingestion_jobs
        SET document_version_id = documents.active_version_id
        FROM documents
        WHERE ingestion_jobs.document_id = documents.id
          AND ingestion_jobs.document_version_id IS NULL
        """,
        """
        UPDATE documents
        SET active_version_id = NULL
        WHERE active_version_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM document_versions
              WHERE document_versions.id = documents.active_version_id
          )
        """,
        """
        UPDATE document_chunks
        SET document_version_id = NULL
        WHERE document_version_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM document_versions
              WHERE document_versions.id = document_chunks.document_version_id
          )
        """,
        """
        UPDATE ingestion_jobs
        SET document_version_id = NULL
        WHERE document_version_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM document_versions
              WHERE document_versions.id = ingestion_jobs.document_version_id
          )
        """,
    ]
    try:
        with engine.begin() as conn:
            for statement in dml_statements:
                conn.exec_driver_sql(statement)
    except Exception as exc:
        logger.warning("document_version_dml_failed", error=str(exc))

    # Phase 3: Foreign-key constraints (DDL, but safe to skip on first run)
    fk_statements = [
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_active_version_id_fkey",
        (
            "ALTER TABLE documents ADD CONSTRAINT documents_active_version_id_fkey "
            "FOREIGN KEY (active_version_id) REFERENCES document_versions(id) ON DELETE SET NULL"
        ),
        (
            "ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS "
            "document_chunks_document_version_id_fkey"
        ),
        (
            "ALTER TABLE document_chunks ADD CONSTRAINT document_chunks_document_version_id_fkey "
            "FOREIGN KEY (document_version_id) REFERENCES document_versions(id) "
            "ON DELETE SET NULL"
        ),
        (
            "ALTER TABLE ingestion_jobs DROP CONSTRAINT IF EXISTS "
            "ingestion_jobs_document_version_id_fkey"
        ),
        (
            "ALTER TABLE ingestion_jobs ADD CONSTRAINT ingestion_jobs_document_version_id_fkey "
            "FOREIGN KEY (document_version_id) REFERENCES document_versions(id) "
            "ON DELETE SET NULL"
        ),
    ]
    try:
        with engine.begin() as conn:
            for statement in fk_statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("document_version_fk_failed", error=str(exc))


def _ensure_user_columns() -> None:
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_valid_after TIMESTAMPTZ",
    ]
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("user_columns_ensure_failed", error=str(exc))


def _ensure_document_foreign_keys() -> None:
    statements = [
        f"ALTER TABLE documents ALTER COLUMN uploaded_by SET DEFAULT '{_DELETED_USER_ID}'",
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_uploaded_by_fkey",
        (
            "ALTER TABLE documents ADD CONSTRAINT documents_uploaded_by_fkey "
            "FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET DEFAULT"
        ),
    ]
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("document_foreign_keys_ensure_failed", error=str(exc))


def _ensure_deleted_user() -> None:
    from app.auth.middleware import hash_password

    statement = text(
        """
        INSERT INTO users (id, email, password_hash, role, is_active)
        SELECT :user_id, :email, :password_hash, :role, false
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = :user_id OR email = :email)
        """
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                statement,
                {
                    "user_id": _DELETED_USER_ID,
                    "email": _DELETED_USER_EMAIL,
                    "password_hash": hash_password(token_urlsafe(24)),
                    "role": "pilot_user",
                },
            )
    except Exception as exc:
        logger.warning("deleted_user_ensure_failed", error=str(exc))


def _ensure_workspace_schema() -> None:
    """Create workspace tables/columns and backfill a default "General" workspace.

    Idempotent and safe to run on every boot. Existing single-workspace
    deployments are migrated transparently: all prior documents/sessions/audit/
    cache/analytics rows land in the default workspace, every active user becomes
    a member, and global admins become workspace_admins of it. Phase-separated so
    a data-migration hiccup cannot roll back the schema changes.
    """
    # Phase 1: DDL — tables, columns, indexes.
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            created_by TEXT NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001'
                REFERENCES users(id) ON DELETE SET DEFAULT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS workspace_memberships (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_workspace_memberships_workspace_id_user_id
                UNIQUE (workspace_id, user_id)
        )
        """,
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS workspace_id TEXT",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS workspace_id TEXT",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS workspace_id TEXT",
        "ALTER TABLE semantic_cache ADD COLUMN IF NOT EXISTS workspace_id TEXT",
        "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS workspace_id TEXT",
        "ALTER TABLE query_feedback ADD COLUMN IF NOT EXISTS workspace_id TEXT",
        "ALTER TABLE human_review_queue ADD COLUMN IF NOT EXISTS workspace_id TEXT",
        "CREATE INDEX IF NOT EXISTS ix_workspace_memberships_workspace_id "
        "ON workspace_memberships(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_workspace_memberships_user_id "
        "ON workspace_memberships(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_documents_workspace_id ON documents(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_sessions_workspace_id ON sessions(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_workspace_id ON audit_logs(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_semantic_cache_workspace_id "
        "ON semantic_cache(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_agent_runs_workspace_id ON agent_runs(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_query_feedback_workspace_id "
        "ON query_feedback(workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_human_review_queue_workspace_id "
        "ON human_review_queue(workspace_id)",
    ]
    try:
        with engine.begin() as conn:
            for statement in ddl_statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("workspace_ddl_failed", error=str(exc))
        return

    # Phase 2: Data migration — default workspace, backfill, membership.
    # Bound parameters (text()) keep the sentinel IDs out of the SQL string; none
    # of these statements contain ':'-literals, so the text() bind parser is safe.
    params = {"ws": _DEFAULT_WORKSPACE_ID, "deleted": _DELETED_USER_ID}
    backfill_tables = (
        "documents",
        "sessions",
        "audit_logs",
        "semantic_cache",
        "agent_runs",
        "query_feedback",
        "human_review_queue",
    )
    dml_statements = [
        text(
            """
            INSERT INTO workspaces (id, name, slug, is_active, created_by)
            SELECT :ws, 'General', 'general', true, :deleted
            WHERE NOT EXISTS (SELECT 1 FROM workspaces WHERE id = :ws)
            """
        ),
        *(
            # noqa justified: `table` comes only from the hardcoded backfill_tables
            # tuple above, never user input — the value (:ws) is still bound.
            text(f"UPDATE {table} SET workspace_id = :ws WHERE workspace_id IS NULL")  # noqa: S608
            for table in backfill_tables
        ),
        text(
            """
            INSERT INTO workspace_memberships (id, workspace_id, user_id, role)
            SELECT 'wm-default-' || users.id, :ws, users.id,
                   CASE WHEN users.role = 'admin' THEN 'workspace_admin' ELSE 'member' END
            FROM users
            WHERE users.is_active = true
              AND users.id <> :deleted
              AND NOT EXISTS (
                  SELECT 1 FROM workspace_memberships m
                  WHERE m.workspace_id = :ws AND m.user_id = users.id
              )
            """
        ),
    ]
    try:
        with engine.begin() as conn:
            for dml in dml_statements:
                conn.execute(dml, params)
    except Exception as exc:
        logger.warning("workspace_dml_failed", error=str(exc))

    # Phase 3: tighten constraints now that every row has a workspace.
    constraint_statements = [
        f"ALTER TABLE documents ALTER COLUMN workspace_id SET DEFAULT '{_DEFAULT_WORKSPACE_ID}'",
        "ALTER TABLE documents ALTER COLUMN workspace_id SET NOT NULL",
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_workspace_id_fkey",
        "ALTER TABLE documents ADD CONSTRAINT documents_workspace_id_fkey "
        "FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT",
        f"ALTER TABLE sessions ALTER COLUMN workspace_id SET DEFAULT '{_DEFAULT_WORKSPACE_ID}'",
        "ALTER TABLE sessions ALTER COLUMN workspace_id SET NOT NULL",
        "ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_workspace_id_fkey",
        "ALTER TABLE sessions ADD CONSTRAINT sessions_workspace_id_fkey "
        "FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET DEFAULT",
        f"ALTER TABLE semantic_cache ALTER COLUMN workspace_id "
        f"SET DEFAULT '{_DEFAULT_WORKSPACE_ID}'",
        "ALTER TABLE semantic_cache ALTER COLUMN workspace_id SET NOT NULL",
        "ALTER TABLE semantic_cache DROP CONSTRAINT IF EXISTS semantic_cache_workspace_id_fkey",
        "ALTER TABLE semantic_cache ADD CONSTRAINT semantic_cache_workspace_id_fkey "
        "FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE",
    ]
    try:
        with engine.begin() as conn:
            for statement in constraint_statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("workspace_constraints_failed", error=str(exc))


def _ensure_agentrun_fk() -> None:
    statements = [
        "DELETE FROM agent_runs WHERE session_id NOT IN (SELECT id FROM sessions)",
        "ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS agent_runs_session_fkey",
        (
            "ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_session_fkey "
            "FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE"
        ),
    ]
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("agentrun_fk_ensure_failed", error=str(exc))


def _ensure_tier_config() -> None:
    """Seed Evaluation tier defaults on a completely fresh deployment.

    Safety rules:
    - If ANY tier key already exists in app_config, skip entirely to avoid
      locking an existing deployment that already has more than 5 users.
    - Set ``SAFE4AI_TIER_CONFIG_SKIP=1`` to disable seeding for dev
      deployments that intentionally want no enforcement.

    Seeded values (Evaluation tier):
        tier=evaluation, max_seats=5, monthly_query_limit=5000
        tier_expires_at is intentionally NOT seeded (no expiry by default).
    """
    if os.environ.get("SAFE4AI_TIER_CONFIG_SKIP", "").lower() in {"1", "true", "yes"}:
        logger.info("tier_config_seed_skipped", reason="SAFE4AI_TIER_CONFIG_SKIP is set")
        return

    _TIER_KEYS = frozenset({"tier", "max_seats", "monthly_query_limit", "tier_expires_at"})

    try:
        from app.services.app_config_store import load_app_config, upsert_app_config

        with SessionLocal() as db:
            existing = load_app_config(db)
            if any(k in existing for k in _TIER_KEYS):
                return  # already configured — never overwrite
            upsert_app_config(
                db,
                {"tier": "evaluation", "max_seats": 5, "monthly_query_limit": 5000},
                commit=True,
            )
        logger.info(
            "tier_config_seeded",
            tier="evaluation",
            max_seats=5,
            monthly_query_limit=5000,
        )
    except Exception as exc:
        logger.warning("tier_config_seed_failed", error=str(exc))


def _ensure_qdrant_collection() -> None:
    """Create the default document collection on first boot if it is missing.

    Uses the configured embedding model's known dimension so a cloud-mode
    first boot with e.g. text-embedding-3-small (1536) creates the right
    collection instead of defaulting to the hardcoded 768.  Raises RuntimeError
    on dimension mismatch so startup fails loudly rather than silently producing
    wrong embeddings.
    """
    from app.services.runtime_config import expected_vector_size, load_runtime_config

    with SessionLocal() as db:
        runtime = load_runtime_config(db)
    embedding_model = runtime.embedding_model

    try:
        client = QdrantClient(url=settings.qdrant_url)
        if client.collection_exists(_QDRANT_COLLECTION):
            expected = expected_vector_size(embedding_model)
            if expected is not None:
                info = client.get_collection(_QDRANT_COLLECTION)
                vectors_cfg = info.config.params.vectors
                actual_size: int = (
                    next(iter(vectors_cfg.values())).size  # type: ignore[union-attr]
                    if isinstance(vectors_cfg, dict)
                    else vectors_cfg.size  # type: ignore[union-attr]
                )
                if actual_size != expected:
                    raise RuntimeError(
                        f"Qdrant collection '{_QDRANT_COLLECTION}' has vector size {actual_size} "
                        f"but embedding model '{embedding_model}' requires {expected}. "
                        "Drop and recreate the collection to switch embedding models."
                    )
            return
        create_vector_size = expected_vector_size(embedding_model) or _QDRANT_VECTOR_SIZE
        client.create_collection(
            collection_name=_QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=create_vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.info(
            "qdrant_collection_created",
            collection=_QDRANT_COLLECTION,
            vector_size=create_vector_size,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning("qdrant_collection_ensure_failed", error=str(exc))
    finally:
        _ensure_qdrant_workspace_payload_index()


def _ensure_qdrant_workspace_payload_index() -> None:
    """Index the ``workspace_id`` payload field so workspace filters are fast.

    Idempotent: Qdrant returns an error if the index already exists, which we
    swallow. Runs on both the create and existing-collection paths.
    """
    try:
        client = QdrantClient(url=settings.qdrant_url)
        if not client.collection_exists(_QDRANT_COLLECTION):
            return
        client.create_payload_index(
            collection_name=_QDRANT_COLLECTION,
            field_name="workspace_id",
            field_schema=qmodels.PayloadSchemaType.KEYWORD,
        )
    except Exception as exc:
        logger.debug("qdrant_workspace_payload_index_skipped", error=str(exc))


def _ensure_semantic_cache_dimension() -> None:
    """Warn if the configured embedding dimension does not match SemanticCache."""
    try:
        from app.services.runtime_config import expected_vector_size, load_runtime_config

        with SessionLocal() as db:
            runtime = load_runtime_config(db)
        expected = expected_vector_size(runtime.embedding_model)
        if expected is not None and expected != 768:
            logger.warning(
                "semantic_cache_dimension_mismatch",
                embedding_model=runtime.embedding_model,
                model_dimension=expected,
                cache_column_dimension=768,
                action=(
                    "Cache similarity searches will fail — migrate the query_embedding "
                    "column or switch to a 768-dim model"
                ),
            )
    except Exception as exc:
        logger.warning("semantic_cache_dimension_check_failed", error=str(exc))


def _warn_default_credentials() -> None:
    """Log warnings if the service is running with known-default secrets.

    In enforce_https mode (production), block startup entirely.
    """
    _DEFAULT_SECRET = "68d543ad135bb451bf0e0a26a7fa6cf5151cb1d0b0c6b1366d18f5543a93927e"  # noqa: S105
    _DEFAULT_PG_URL = "postgresql+psycopg2://safe4ai:safe4ai@"
    if settings.secret_key == _DEFAULT_SECRET:
        if settings.enforce_https:
            raise RuntimeError(
                "FATAL: Default SECRET_KEY detected with enforce_https=True. "
                "Rotate SECRET_KEY before running in production."
            )
        logger.warning(
            "default_secret_key_in_use",
            action="Rotate SECRET_KEY before exposing this service to the network",
        )
    if settings.postgres_url.startswith(_DEFAULT_PG_URL):
        if settings.enforce_https:
            raise RuntimeError(
                "FATAL: Default PostgreSQL credentials detected with enforce_https=True. "
                "Change the PostgreSQL password before running in production."
            )
        logger.warning(
            "default_postgres_credentials_in_use",
            action="Change the PostgreSQL password in .env and docker-compose.yml",
        )
