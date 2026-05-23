from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_startup_initializes_pgvector_extension_before_tables() -> None:
    main_py = (ROOT / "app" / "main.py").read_text()

    extension_idx = main_py.index("CREATE EXTENSION IF NOT EXISTS vector")
    create_all_idx = main_py.index("Base.metadata.create_all")

    assert extension_idx < create_all_idx


def test_startup_creates_schema_before_recovering_jobs() -> None:
    main_py = (ROOT / "app" / "main.py").read_text()

    create_all_idx = main_py.index("Base.metadata.create_all")
    recover_idx = main_py.index("recover_stuck_jobs(db)")

    assert create_all_idx < recover_idx


# ---------------------------------------------------------------------------
# _ensure_qdrant_collection create path
# ---------------------------------------------------------------------------

class TestEnsureQdrantCollectionCreate:
    """Verify that _ensure_qdrant_collection passes the model's known dimension
    to create_collection on first boot instead of the hardcoded 768 fallback.

    This directly locks the riskiest bug: a cloud-mode first boot with
    text-embedding-3-small must create a 1536-dim collection, not a 768-dim one.
    """

    def _run(self, embedding_model: str) -> MagicMock:
        """Return the QdrantClient mock after running _ensure_qdrant_collection."""
        fake_runtime = MagicMock()
        fake_runtime.embedding_model = embedding_model

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False

        with (
            patch(
                "app.services.runtime_config.load_runtime_config",
                return_value=fake_runtime,
            ),
            patch(
                "app.startup_migrations.SessionLocal",
            ),
            patch(
                "app.startup_migrations.QdrantClient",
                return_value=mock_client,
            ),
        ):
            from app.startup_migrations import _ensure_qdrant_collection
            _ensure_qdrant_collection()

        return mock_client

    def test_text_embedding_3_small_creates_1536_dim_collection(self) -> None:
        mock_client = self._run("text-embedding-3-small")

        mock_client.create_collection.assert_called_once()
        _, kwargs = mock_client.create_collection.call_args
        assert kwargs["vectors_config"].size == 1536

    def test_text_embedding_3_large_creates_3072_dim_collection(self) -> None:
        mock_client = self._run("text-embedding-3-large")

        mock_client.create_collection.assert_called_once()
        _, kwargs = mock_client.create_collection.call_args
        assert kwargs["vectors_config"].size == 3072

    def test_nomic_embed_text_creates_768_dim_collection(self) -> None:
        mock_client = self._run("nomic-embed-text")

        mock_client.create_collection.assert_called_once()
        _, kwargs = mock_client.create_collection.call_args
        assert kwargs["vectors_config"].size == 768

    def test_unknown_model_falls_back_to_768(self) -> None:
        mock_client = self._run("some-unknown-model-v9")

        mock_client.create_collection.assert_called_once()
        _, kwargs = mock_client.create_collection.call_args
        assert kwargs["vectors_config"].size == 768

    def test_dimension_mismatch_raises_on_existing_collection(self) -> None:
        """A collection that already exists with the wrong size must raise RuntimeError."""
        fake_runtime = MagicMock()
        fake_runtime.embedding_model = "text-embedding-3-small"  # expects 1536

        vectors_cfg = MagicMock()
        vectors_cfg.size = 768  # wrong — collection was created with nomic-embed-text
        fake_info = MagicMock()
        fake_info.config.params.vectors = vectors_cfg

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_client.get_collection.return_value = fake_info

        with (
            patch("app.services.runtime_config.load_runtime_config", return_value=fake_runtime),
            patch("app.startup_migrations.SessionLocal"),
            patch("app.startup_migrations.QdrantClient", return_value=mock_client),
            pytest.raises(RuntimeError, match="1536"),
        ):
            from app.startup_migrations import _ensure_qdrant_collection
            _ensure_qdrant_collection()
