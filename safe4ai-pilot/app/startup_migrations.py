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
from app.db.models import DELETED_USER_ID

logger = structlog.get_logger(__name__)

_QDRANT_COLLECTION = "documents"
_QDRANT_VECTOR_SIZE = 768
_DELETED_USER_ID = DELETED_USER_ID  # alias kept so call-sites below are unchanged
_DELETED_USER_EMAIL = "deleted@redacted.local"


def run_startup_migrations() -> None:
    """Run all boot-time schema fixes and sanity checks in order."""
    _ensure_documents_columns()
    _ensure_document_version_schema()
    _ensure_user_columns()
    _ensure_document_foreign_keys()
    _ensure_agentrun_fk()
    _ensure_deleted_user()
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
