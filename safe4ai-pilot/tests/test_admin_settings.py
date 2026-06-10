"""Admin settings route tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.db.models import User
from tests.helpers.admin_routes import (
    make_admin_user as _make_admin_user,
)
from tests.helpers.admin_routes import (
    make_test_client as _make_test_client,
)
from tests.helpers.admin_routes import (
    mock_db_with_admin as _mock_db_with_admin,
)


class TestSettings:
    def test_get_settings_uses_live_cost_stats(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.count.return_value = 4

        with patch("pathlib.Path.mkdir"), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 12.34, "runs_count": 3, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.get("/settings")

        assert resp.status_code == 200
        assert resp.json()["cost"]["todayUsd"] == pytest.approx(12.34)
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_returns_full_settings_payload(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if model is User else None
        updated_generation = MagicMock()
        updated_generation.key = "generation_model"
        updated_generation.value = "qwen3:latest"
        db.query.return_value.all.side_effect = [
            [],
            [updated_generation],
            [updated_generation],
        ]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={"qwen3:latest"},
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"generationModel": "qwen3:latest"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["generationModel"] == "qwen3:latest"
        assert "cost" in body
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_persists_normalized_blocked_terms(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.scalar.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch(
                "/settings",
                json={"blockedTerms": [" MRN ", "patient identifier", ""]},
            )

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        assert updates["blocked_terms"] == ["mrn", "patient identifier"]
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_settings_includes_blocked_terms(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        blocked_terms = MagicMock()
        blocked_terms.key = "blocked_terms"
        blocked_terms.value = ["mrn", "patient identifier"]
        db.query.return_value.all.return_value = [blocked_terms]
        db.query.return_value.scalar.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ), patch(
            "app.services.settings_service._settings_live_cache", {"expires_at": 0.0}
        ):
            client = _make_test_client(db, admin)
            resp = client.get("/settings")

        assert resp.status_code == 200
        assert resp.json()["security"]["blockedTerms"] == ["mrn", "patient identifier"]
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_persists_oidc_config(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.scalar.return_value = 0
        provider_url_patch = patch(
            "app.services.settings_service.validate_provider_url",
            return_value=("https://idp.example.com", "93.184.216.34"),
        )

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), provider_url_patch, patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch(
                "/settings",
                json={
                    "oidcEnabled": True,
                    "oidcIssuerUrl": "https://idp.example.com/",
                    "oidcClientId": "safe4ai",
                    "oidcClientSecret": "secret-value",
                    "oidcRedirectUri": "http://localhost:8000/auth/sso/callback",
                    "oidcAllowedDomains": [" Example.com ", ""],
                    "oidcAutoProvision": True,
                },
            )

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        assert updates["oidc_enabled"] is True
        assert updates["oidc_issuer_url"] == "https://idp.example.com"
        assert updates["oidc_client_id"] == "safe4ai"
        assert updates["oidc_client_secret"] == "secret-value"  # noqa: S105
        assert updates["oidc_allowed_domains"] == ["example.com"]
        assert updates["oidc_auto_provision"] is True
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_settings_exposes_oidc_without_secret(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        rows = []
        for key, value in {
            "oidc_enabled": True,
            "oidc_issuer_url": "https://idp.example.com",
            "oidc_client_id": "safe4ai",
            "oidc_client_secret": "secret-value",
            "oidc_redirect_uri": "http://localhost:8000/auth/sso/callback",
            "oidc_allowed_domains": ["example.com"],
            "oidc_auto_provision": False,
        }.items():
            row = MagicMock()
            row.key = key
            row.value = value
            rows.append(row)
        db.query.return_value.all.return_value = rows
        db.query.return_value.scalar.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ), patch(
            "app.services.settings_service._settings_live_cache", {"expires_at": 0.0}
        ):
            client = _make_test_client(db, admin)
            resp = client.get("/settings")

        assert resp.status_code == 200
        oidc = resp.json()["security"]["oidc"]
        assert oidc["enabled"] is True
        assert oidc["configured"] is True
        assert oidc["clientSecretConfigured"] is True
        assert "secret-value" not in str(resp.json())
        from app.main import app
        app.dependency_overrides.clear()

    def test_fetch_provider_model_names_validates_stored_url(self) -> None:
        from app.services.settings_service import _fetch_provider_model_names

        response = MagicMock()
        response.json.return_value = {"data": [{"id": "model-a"}]}
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = response

        with patch(
            "app.services.settings_service.validate_provider_url",
            return_value=("https://provider.example/v1", "203.0.113.10"),
        ) as mock_validate, patch(
            "app.services.settings_service.httpx.Client",
            return_value=client,
        ):
            models = _fetch_provider_model_names("https://provider.example/v1", "sk-test")

        assert models == ["model-a"]
        mock_validate.assert_called_once_with("https://provider.example/v1")

    def test_embedding_dimension_check_logs_qdrant_errors(self) -> None:
        from app.services.settings_service import _validate_embedding_model_dimension

        qdrant = MagicMock()
        qdrant.get_collection.side_effect = RuntimeError("qdrant unavailable")

        with patch("app.services.settings_service._QdrantClient", return_value=qdrant), patch(
            "app.services.settings_service.logger.debug"
        ) as mock_debug:
            _validate_embedding_model_dimension("nomic-embed-text")

        mock_debug.assert_called_once()
        assert mock_debug.call_args.args[0] == "embedding_dim_check_skipped"

    def test_patch_openai_generation_model_updates_provider_chat_model(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        provider_type = MagicMock()
        provider_type.key = "provider_type"
        provider_type.value = "openai_compatible"
        provider_api_key = MagicMock()
        provider_api_key.key = "provider_api_key"
        provider_api_key.value = "sk-test"
        db.query.return_value.all.return_value = [provider_type, provider_api_key]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"generationModel": "deepseek-flash"})

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        assert updates["generation_model"] == "deepseek-flash"
        assert updates["provider_chat_model"] == "deepseek-flash"
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_rejects_unknown_ollama_model(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)

        with patch("pathlib.Path.mkdir"), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={"known:model"},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"generationModel": "missing:model"})

        assert resp.status_code == 422
        assert resp.json()["detail"] == "generationModel is not available in Ollama"
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_settings_includes_available_model_options(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={"qwen3.5:9b", "nomic-embed-text"},
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ), patch.dict(
            "app.services.settings_service._settings_live_cache", {"expires_at": 0.0}
        ):
            client = _make_test_client(db, admin)
            resp = client.get("/settings")

        assert resp.status_code == 200
        body = resp.json()
        assert body["availableModels"]["ollama"] == [
            "nomic-embed-text",
            "qwen3.5:9b",
        ]
        assert "bge-reranker-v2" in body["availableModels"]["reranker"]
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_rolls_back_when_runtime_rebuild_fails(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.get.side_effect = lambda model, pk: admin if model is User else None
        db.query.return_value.all.return_value = []

        with patch("pathlib.Path.mkdir"), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={"qwen3:latest"},
        ), patch(
            "app.api.settings_routes.build_runtime_components",
            side_effect=RuntimeError("bad provider config"),
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"generationModel": "qwen3:latest"})

        assert resp.status_code == 422
        assert "Configuration is invalid and was not saved" in resp.json()["detail"]
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
        from app.main import app
        app.dependency_overrides.clear()

    def test_get_settings_includes_custom_provider_models(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        custom_models = MagicMock()
        custom_models.key = "custom_provider_models"
        custom_models.value = ["deepseek-v4-flash", "qwen-plus"]
        db.query.return_value.all.return_value = [custom_models]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value=set(),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ), patch.dict(
            "app.services.settings_service._settings_live_cache", {"expires_at": 0.0}
        ):
            client = _make_test_client(db, admin)
            resp = client.get("/settings")

        assert resp.status_code == 200
        body = resp.json()
        assert body["availableModels"]["customProvider"] == ["deepseek-v4-flash", "qwen-plus"]
        assert "deepseek-v4-flash" in body["availableModels"]["provider"]
        assert "qwen-plus" in body["availableModels"]["provider"]
        from app.main import app
        app.dependency_overrides.clear()

    def test_serialize_settings_includes_provider_mode_and_embedding_source(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        provider_type = MagicMock()
        provider_type.key = "provider_type"
        provider_type.value = "openai_compatible"
        embedding_source = MagicMock()
        embedding_source.key = "embedding_source"
        embedding_source.value = "ollama"
        db.query.return_value.all.return_value = [provider_type, embedding_source]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value=set(),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ), patch.dict(
            "app.services.settings_service._settings_live_cache", {"expires_at": 0.0}
        ):
            client = _make_test_client(db, admin)
            resp = client.get("/settings")

        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"]["embeddingSource"] == "ollama"
        assert body["provider"]["providerMode"] == "hybrid"
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_provider_mode_local_does_not_persist_base_url(self) -> None:
        """PATCH providerMode=local must not persist provider_base_url.

        Local Ollama's URL is env-owned (effective_provider_base_url); persisting
        it is how host-vs-Docker URLs used to leak between runtimes.
        """
        from app.config import settings as app_settings

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={app_settings.ollama_model, app_settings.embedding_model},
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "local"})

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        assert updates["provider_type"] == "ollama"
        assert updates["embedding_source"] == "ollama"
        assert "provider_base_url" not in updates
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_provider_mode_local_sets_correct_fields(self) -> None:
        from app.config import settings as app_settings

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={app_settings.ollama_model, app_settings.embedding_model},
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "local"})

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        assert updates["provider_type"] == "ollama"
        assert updates["embedding_source"] == "ollama"
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_provider_mode_hybrid_sets_correct_fields(self) -> None:
        """PATCH providerMode=hybrid: provider_type=openai_compatible, embedding_source=ollama."""
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        provider_api_key = MagicMock()
        provider_api_key.key = "provider_api_key"
        provider_api_key.value = "sk-test"
        embedding_model_cfg = MagicMock()
        embedding_model_cfg.key = "embedding_model"
        embedding_model_cfg.value = "nomic-embed-text"
        db.query.return_value.all.return_value = [provider_api_key, embedding_model_cfg]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={"nomic-embed-text", "qwen3.5:9b"},
        ), patch(
            # validate_provider_url calls socket.getaddrinfo — bypass DNS in tests
            "app.services.settings_service.validate_provider_url",
            side_effect=lambda url: (url.rstrip("/"), "93.184.216.34"),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "hybrid"})

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        assert updates["provider_type"] == "openai_compatible"
        assert updates["embedding_source"] == "ollama"
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_provider_mode_hybrid_fails_when_ollama_unreachable(self) -> None:
        """PATCH providerMode=hybrid must return 422 when Ollama is not reachable."""
        from app.services.settings_exceptions import SettingsValidationError

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        provider_api_key = MagicMock()
        provider_api_key.key = "provider_api_key"
        provider_api_key.value = "sk-test"
        db.query.return_value.all.return_value = [provider_api_key]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            side_effect=SettingsValidationError("Ollama unreachable"),
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "hybrid"})

        assert resp.status_code == 422
        assert "Ollama" in resp.json()["detail"]
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_provider_mode_hybrid_auto_resets_cloud_embedding_model(self) -> None:
        """Switching to hybrid auto-resets cloud-only embedding model to default."""
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        provider_api_key = MagicMock()
        provider_api_key.key = "provider_api_key"
        provider_api_key.value = "sk-test"
        # Previous cloud config had a cloud-only embedding model
        embedding_model_cfg = MagicMock()
        embedding_model_cfg.key = "embedding_model"
        embedding_model_cfg.value = "text-embedding-3-small"
        db.query.return_value.all.return_value = [provider_api_key, embedding_model_cfg]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            # text-embedding-3-small is NOT in Ollama, but nomic-embed-text and vision default are
            return_value={"nomic-embed-text", "qwen3.5:9b"},
        ), patch(
            # validate_provider_url calls socket.getaddrinfo — bypass DNS in tests
            "app.services.settings_service.validate_provider_url",
            side_effect=lambda url: (url.rstrip("/"), "93.184.216.34"),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "hybrid"})

        # Should succeed (auto-reset) instead of 422
        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        from app.config import settings as app_settings
        assert updates.get("embedding_model") == app_settings.embedding_model
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_provider_mode_invalid_returns_422(self) -> None:
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "datacenter"})

        assert resp.status_code == 422
        assert "providerMode" in resp.json()["detail"]
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_local_resets_stale_cloud_chat_model(self) -> None:
        """cloud → local: a cloud chat model in generation_model is reset to the Ollama default."""
        from app.config import settings as app_settings

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        # DB has cloud generation_model from a previous cloud session
        gen_model_cfg = MagicMock()
        gen_model_cfg.key = "generation_model"
        gen_model_cfg.value = "deepseek-v4-flash"
        db.query.return_value.all.return_value = [gen_model_cfg]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            # deepseek-v4-flash is NOT in Ollama; only the Ollama defaults are
            return_value={app_settings.ollama_model, app_settings.embedding_model},
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "local"})

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        # generation_model must be reset to a valid Ollama model, not left as the cloud ID
        assert updates["generation_model"] == app_settings.ollama_model
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_local_resets_stale_cloud_embedding_and_vision_models(self) -> None:
        """cloud → local: cloud embedding and vision models are reset to Ollama defaults."""
        from app.config import settings as app_settings

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        emb_cfg = MagicMock()
        emb_cfg.key = "embedding_model"
        emb_cfg.value = "text-embedding-3-small"
        vis_cfg = MagicMock()
        vis_cfg.key = "vision_model"
        vis_cfg.value = "qwen-vl-plus"
        db.query.return_value.all.return_value = [emb_cfg, vis_cfg]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={app_settings.ollama_model, app_settings.embedding_model},
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "local"})

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        assert updates["embedding_model"] == app_settings.embedding_model
        assert updates["vision_model"] == "qwen3.5:9b"
        from app.main import app
        app.dependency_overrides.clear()

    def test_patch_settings_hybrid_resets_stale_cloud_vision_model(self) -> None:
        """cloud → hybrid: a cloud vision model in vision_model is reset to the Ollama default."""
        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        provider_api_key = MagicMock()
        provider_api_key.key = "provider_api_key"
        provider_api_key.value = "sk-test"
        emb_cfg = MagicMock()
        emb_cfg.key = "embedding_model"
        emb_cfg.value = "nomic-embed-text"
        vis_cfg = MagicMock()
        vis_cfg.key = "vision_model"
        vis_cfg.value = "qwen-vl-plus"  # stale cloud vision model
        db.query.return_value.all.return_value = [provider_api_key, emb_cfg, vis_cfg]
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ) as mock_upsert, patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            # Both embedding AND vision defaults must be present so the sanitization can reset
            return_value={"nomic-embed-text", "qwen3.5:9b"},
        ), patch(
            "app.services.settings_service.validate_provider_url",
            side_effect=lambda url: (url.rstrip("/"), "93.184.216.34"),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"providerMode": "hybrid"})

        assert resp.status_code == 200
        updates = mock_upsert.call_args.args[1]
        # vision_model must be reset to the Ollama default, not left as the cloud vision ID
        assert updates["vision_model"] == "qwen3.5:9b"
        from app.main import app
        app.dependency_overrides.clear()

    def test_provider_change_creates_audit_log(self) -> None:
        """PATCH /settings with provider config creates a provider-change audit log."""
        from app.db.models import AuditLog as AuditLogModel

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0
        db.get.side_effect = lambda model, pk: admin if model is User else None

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ), patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.validate_provider_url",
            return_value=("https://idp.example.com", "93.184.216.34"),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={"qwen3.5:9b"},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch(
                "/settings",
                json={"providerType": "openai_compatible", "providerApiKey": "sk-test"},
            )

        assert resp.status_code == 200
        # db.add must have been called with at least one AuditLog for provider change
        added_audit_logs = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], AuditLogModel)
        ]
        assert len(added_audit_logs) == 1
        assert added_audit_logs[0].action_type == "settings_provider_change"
        from app.main import app
        app.dependency_overrides.clear()

    def test_non_provider_change_does_not_create_provider_audit(self) -> None:
        """PATCH /settings with only a retrieval param must NOT create a provider audit row."""
        from app.db.models import AuditLog as AuditLogModel

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ), patch(
            "app.api.settings_routes.build_runtime_components",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch(
            "app.services.settings_service.validate_provider_url",
            return_value=("https://idp.example.com", "93.184.216.34"),
        ), patch(
            "observability.cost_tracker.CostTracker.get_stats",
            return_value={"total_cost_usd": 0.0, "runs_count": 0, "by_day": []},
        ), patch(
            "app.services.settings_service.fetch_ollama_model_names",
            return_value={"qwen3.5:9b"},
        ):
            client = _make_test_client(db, admin)
            resp = client.patch("/settings", json={"retrievalK": 8})

        assert resp.status_code == 200
        provider_audit_logs = [
            call.args[0]
            for call in db.add.call_args_list
            if isinstance(call.args[0], AuditLogModel)
            and getattr(call.args[0], "action_type", "") == "settings_provider_change"
        ]
        assert len(provider_audit_logs) == 0
        from app.main import app
        app.dependency_overrides.clear()

    def test_provider_audit_rollback_on_build_failure(self) -> None:
        """When build_runtime_components fails, settings and audit log are both rolled back."""

        admin = _make_admin_user()
        db = _mock_db_with_admin(admin)
        db.query.return_value.all.return_value = []
        db.get.side_effect = lambda model, pk: admin if model is User else None

        with patch("pathlib.Path.mkdir"), patch(
            "app.api.settings_routes.upsert_app_config"
        ), patch(
            "app.api.settings_routes.build_runtime_components",
            side_effect=RuntimeError("Qdrant not reachable"),
        ):
            client = _make_test_client(db, admin)
            resp = client.patch(
                "/settings",
                json={"providerType": "openai_compatible", "providerApiKey": "sk-test"},
            )

        assert resp.status_code == 422
        assert "invalid" in resp.json()["detail"].lower()
        # db.rollback must have been called; db.commit must NOT have been called
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
        from app.main import app
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
