from datetime import UTC
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_private_ai_state_defaults_are_isolated() -> None:
    from app.models import Message, PrivateAIState

    first = PrivateAIState(session_id="s1", user_id="u1")
    second = PrivateAIState(session_id="s2", user_id="u2")

    first.messages.append(Message(role="user", content="hello"))
    first.errors.append("example")

    assert len(first.messages) == 1
    assert second.messages == []
    assert second.errors == []
    assert first.messages[0].created_at.tzinfo == UTC


def test_database_metadata_contains_phase_one_tables() -> None:
    import app.db.models  # noqa: F401
    from app.db import Base

    expected_tables = {
        "users",
        "sessions",
        "documents",
        "document_chunks",
        "semantic_cache",
        "semantic_cache_hits",
        "audit_logs",
        "agent_runs",
        "query_feedback",
        "ingestion_jobs",
        "human_review_queue",
        "document_versions",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))


def test_document_and_semantic_cache_columns_match_plan() -> None:
    from app.db.models import (
        Document,
        DocumentChunk,
        DocumentVersion,
        DocumentVersionStatus,
        IngestionJob,
        IngestionStatus,
        SemanticCache,
    )

    document_columns = set(Document.__table__.columns.keys())
    chunk_columns = set(DocumentChunk.__table__.columns.keys())
    version_columns = set(DocumentVersion.__table__.columns.keys())
    job_columns = set(IngestionJob.__table__.columns.keys())
    cache_columns = set(SemanticCache.__table__.columns.keys())

    assert {
        "active_version_id",
        "title",
    }.issubset(document_columns)
    assert {
        "id",
        "document_id",
        "version_number",
        "filename",
        "storage_filename",
        "file_type",
        "file_size_bytes",
        "checksum",
        "status",
        "created_by",
        "created_at",
        "ingestion_started_at",
        "ingested_at",
        "activated_at",
        "failed_at",
        "failed_reason",
    }.issubset(version_columns)
    assert {"chunk_version", "document_version_id"}.issubset(chunk_columns)
    assert "document_version_id" in job_columns
    assert {"source_document_ids", "source_chunk_ids"}.issubset(cache_columns)
    assert DocumentVersionStatus.pending.value == "pending"
    assert DocumentVersionStatus.active.value == "active"
    assert DocumentVersionStatus.superseded.value == "superseded"
    assert IngestionStatus.skipped.value == "skipped"


def test_document_uploaded_by_fk_has_delete_default_protection() -> None:
    from app.db.models import Document

    uploaded_by = Document.__table__.c.uploaded_by
    fk = next(iter(uploaded_by.foreign_keys))

    assert uploaded_by.server_default is not None
    assert fk.ondelete == "SET DEFAULT"


def test_settings_parse_allowed_origins() -> None:
    from app.config import Settings

    settings = Settings(allowed_origins="http://localhost:5173, https://example.com")

    assert settings.allowed_origins_list == ["http://localhost:5173", "https://example.com"]


def test_settings_default_allowed_origin_matches_vite_dev_port() -> None:
    from app.config import Settings

    settings = Settings()

    assert settings.allowed_origins_list == ["http://localhost:3000"]


def test_runtime_config_coerce_bool_handles_string_zero() -> None:
    from app.services.runtime_config import _coerce_bool

    assert _coerce_bool("0", True) is False
    assert _coerce_bool("false", True) is False
    assert _coerce_bool("1", False) is True


def test_load_app_config_coerces_boolean_strings_explicitly() -> None:
    from app.services.app_config_store import load_app_config

    db = MagicMock()
    db.query.return_value.all.return_value = [
        SimpleNamespace(key="sso_only", value="false"),
        SimpleNamespace(key="redact_pii", value="0"),
        SimpleNamespace(key="reranker_enabled", value="off"),
    ]

    config = load_app_config(db)

    assert config["sso_only"] is False
    assert config["redact_pii"] is False
    assert config["reranker_enabled"] is False


def test_upsert_app_config_encrypts_provider_api_key() -> None:
    from app.db.models import AppConfig
    from app.services.app_config_store import load_app_config, upsert_app_config

    rows: dict[str, AppConfig] = {}
    db = MagicMock()
    db.get.side_effect = lambda _model, key: rows.get(key)
    db.add.side_effect = lambda row: rows.setdefault(row.key, row)
    db.query.return_value.all.side_effect = lambda: list(rows.values())

    upsert_app_config(db, {"provider_api_key": "sk-secret"}, commit=False)

    stored = rows["provider_api_key"].value
    assert isinstance(stored, str)
    assert stored.startswith("enc:")
    assert "sk-secret" not in stored
    assert load_app_config(db)["provider_api_key"] == "sk-secret"


@pytest.mark.asyncio
async def test_prewarm_provider_skips_non_ollama() -> None:
    from app.main import _prewarm_provider

    runtime = type(
        "Runtime",
        (),
        {"provider_type": "openai_compatible", "chat_model": "DeepSeek-V4-Flash"},
    )()
    with pytest.MonkeyPatch.context() as mp:
        called = {"post": False}

        class _Client:
            async def __aenter__(self) -> "_Client":
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

            async def post(self, *_args: object, **_kwargs: object) -> None:
                called["post"] = True

        mp.setattr("app.main.httpx.AsyncClient", lambda timeout=120: _Client())
        await _prewarm_provider(runtime)

    assert called["post"] is False
