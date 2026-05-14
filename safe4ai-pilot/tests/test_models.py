from datetime import UTC


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
        "audit_logs",
        "agent_runs",
        "query_feedback",
        "ingestion_jobs",
        "human_review_queue",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))


def test_document_and_semantic_cache_columns_match_plan() -> None:
    from app.db.models import Document, DocumentChunk, IngestionStatus, SemanticCache

    document_columns = set(Document.__table__.columns.keys())
    chunk_columns = set(DocumentChunk.__table__.columns.keys())
    cache_columns = set(SemanticCache.__table__.columns.keys())

    assert {"version", "active_version"}.issubset(document_columns)
    assert "chunk_version" in chunk_columns
    assert {"source_document_ids", "source_chunk_ids"}.issubset(cache_columns)
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
