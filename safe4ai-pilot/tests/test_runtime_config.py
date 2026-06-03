from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.provider_clients import OllamaProvider, OpenAICompatibleProvider
from app.services.runtime_config import (
    build_embedding_provider,
    build_provider,
    build_vision_provider,
    load_runtime_config,
)


def test_runtime_config_defaults_to_ollama_provider() -> None:
    db = MagicMock()
    with patch("app.services.runtime_config.load_app_config", return_value={}):
        runtime = load_runtime_config(db)

    assert runtime.provider_type == "ollama"
    assert runtime.provider_base_url.startswith("http")
    assert runtime.provider_api_key is None
    assert runtime.chat_model == runtime.generation_model
    assert runtime.usage_source == "estimated"


def test_runtime_config_loads_openai_compatible_provider() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
            "provider_chat_model": "deepseek-v4-flash",
            "provider_embedding_model": "text-embedding-3-small",
            "provider_vision_model": "qwen-vl-plus",
            "sse_done_mode": "async",
        },
    ):
        runtime = load_runtime_config(db)

    assert runtime.provider_type == "openai_compatible"
    assert runtime.provider_base_url == "https://api.deepseek.com/v1"
    assert runtime.provider_api_key == "sk-test"
    assert runtime.chat_model == "deepseek-v4-flash"
    assert runtime.embedding_model == "text-embedding-3-small"
    assert runtime.vision_model == "qwen-vl-plus"
    assert runtime.sse_done_mode == "async"
    assert runtime.usage_source == "actual"


def test_runtime_config_loads_provider_resolved_ip() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
        },
    ):
        runtime = load_runtime_config(db)

    assert runtime.provider_resolved_ip == "93.184.216.34"


def test_runtime_config_resolves_legacy_provider_without_stored_ip() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_api_key": "sk-test",
        },
    ), patch(
        "app.services.runtime_config.validate_provider_url",
        return_value=("https://api.deepseek.com/v1", "93.184.216.34"),
    ) as mock_validate:
        runtime = load_runtime_config(db)

    assert runtime.provider_resolved_ip == "93.184.216.34"
    mock_validate.assert_called_once_with("https://api.deepseek.com/v1")


def test_build_provider_pins_openai_compatible_transport() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
        },
    ), patch("app.services.provider_clients.create_pinned_async_transport") as mock_transport:
        runtime = load_runtime_config(db)
        build_provider(runtime)

    mock_transport.assert_called_once_with("https://api.deepseek.com/v1", "93.184.216.34")


def test_runtime_config_invalid_provider_type_falls_back_to_ollama() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={"provider_type": "unknown_provider"},
    ):
        runtime = load_runtime_config(db)

    assert runtime.provider_type == "ollama"


def test_build_runtime_components_uses_openai_provider_clients() -> None:
    from app.services.runtime_config import build_runtime_components

    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.example.com/v1",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
            "provider_chat_model": "qwen-plus",
            "provider_embedding_model": "text-embedding-3-small",
        },
    ), patch("app.services.runtime_config.build_graph") as mock_build_graph, patch(
        "app.services.runtime_config.HybridRetriever"
    ) as mock_retriever_cls, patch(
        "app.services.runtime_config.Reranker"
    ):
        mock_retriever = MagicMock()
        mock_retriever.embedding_model = "text-embedding-3-small"
        mock_retriever_cls.return_value = mock_retriever

        runtime, retriever, reranker, graph = build_runtime_components(db)

    assert runtime.provider_type == "openai_compatible"
    assert retriever.embedding_model == "text-embedding-3-small"
    mock_build_graph.assert_called_once()


# ---------------------------------------------------------------------------
# provider_mode derived property
# ---------------------------------------------------------------------------


def test_provider_mode_local_when_ollama() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={"provider_type": "ollama"},
    ):
        runtime = load_runtime_config(db)
    assert runtime.provider_mode == "local"


def test_provider_mode_hybrid_when_openai_and_ollama_embeddings() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
            "embedding_source": "ollama",
        },
    ):
        runtime = load_runtime_config(db)
    assert runtime.provider_mode == "hybrid"
    assert runtime.embedding_source == "ollama"


def test_provider_mode_cloud_when_openai_and_provider_embeddings() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
            "embedding_source": "provider",
        },
    ):
        runtime = load_runtime_config(db)
    assert runtime.provider_mode == "cloud"


def test_openai_compatible_without_embedding_source_defaults_to_provider() -> None:
    """openai_compatible without embedding_source in DB defaults to cloud (backward compat)."""
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
        },
    ):
        runtime = load_runtime_config(db)
    assert runtime.embedding_source == "provider"
    assert runtime.provider_mode == "cloud"


def test_runtime_config_loads_blocked_terms() -> None:
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={"blocked_terms": ["MRN", "patient identifier", "  "]},
    ):
        runtime = load_runtime_config(db)

    assert runtime.blocked_terms == ["mrn", "patient identifier"]


def test_build_runtime_components_passes_blocked_terms_to_graph() -> None:
    from app.services.runtime_config import build_runtime_components

    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={"blocked_terms": ["confidential"]},
    ), patch("app.services.runtime_config.build_graph") as mock_build_graph, patch(
        "app.services.runtime_config.HybridRetriever"
    ), patch(
        "app.services.runtime_config.Reranker"
    ):
        build_runtime_components(db)

    assert mock_build_graph.call_args.kwargs["blocked_terms"] == ["confidential"]


# ---------------------------------------------------------------------------
# build_embedding_provider and build_vision_provider factories
# ---------------------------------------------------------------------------


def test_build_embedding_provider_hybrid_returns_ollama() -> None:
    """In hybrid mode (embedding_source=ollama), build_embedding_provider returns OllamaProvider."""
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_api_key": "sk-test",
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_resolved_ip": "93.184.216.34",
            "embedding_source": "ollama",
        },
    ):
        runtime = load_runtime_config(db)

    provider = build_embedding_provider(runtime)
    assert isinstance(provider, OllamaProvider)


def test_build_embedding_provider_cloud_returns_openai_compatible() -> None:
    """Cloud mode (embedding_source=provider): build_embedding_provider returns OpenAICompatible."""
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_api_key": "sk-test",
            "provider_base_url": "https://api.openai.com/v1",
            "provider_resolved_ip": "93.184.216.34",
            "embedding_source": "provider",
        },
    ):
        runtime = load_runtime_config(db)

    provider = build_embedding_provider(runtime)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_build_vision_provider_hybrid_uses_local_ollama() -> None:
    """Hybrid mode: build_vision_provider always returns OllamaProvider (vision model is local)."""
    db = MagicMock()
    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
            "embedding_source": "ollama",
        },
    ):
        runtime = load_runtime_config(db)

    provider = build_vision_provider(runtime)
    assert isinstance(provider, OllamaProvider)


def test_build_runtime_components_hybrid_splits_providers() -> None:
    """Hybrid: chat uses OpenAICompatible; HybridRetriever uses OllamaProvider for embeddings."""
    from app.services.runtime_config import build_runtime_components

    db = MagicMock()
    captured: dict = {}

    def _capture_retriever(**kwargs):  # type: ignore[no-untyped-def]
        captured["embedding_client"] = kwargs.get("embedding_client")
        return MagicMock()

    with patch(
        "app.services.runtime_config.load_app_config",
        return_value={
            "provider_type": "openai_compatible",
            "provider_base_url": "https://api.deepseek.com/v1",
            "provider_resolved_ip": "93.184.216.34",
            "provider_api_key": "sk-test",
            "embedding_source": "ollama",
        },
    ), patch("app.services.runtime_config.build_graph") as mock_build_graph, patch(
        "app.services.runtime_config.HybridRetriever",
        side_effect=lambda **kw: _capture_retriever(**kw),
    ), patch(
        "app.services.runtime_config.Reranker"
    ):
        runtime, _retriever, _reranker, _graph = build_runtime_components(db)

    assert isinstance(captured["embedding_client"], OllamaProvider), (
        "embedding_client must be OllamaProvider in hybrid mode"
    )
    # chat_client passed to build_graph must be OpenAICompatibleProvider
    call_kwargs = mock_build_graph.call_args.kwargs
    assert isinstance(call_kwargs["chat_client"], OpenAICompatibleProvider), (
        "chat_client must be OpenAICompatibleProvider in hybrid mode"
    )
