from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.runtime_config import load_runtime_config


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
            "provider_api_key": "sk-test",
            "provider_chat_model": "deepseek-chat",
            "provider_embedding_model": "text-embedding-3-small",
            "provider_vision_model": "qwen-vl-plus",
            "sse_done_mode": "async",
        },
    ):
        runtime = load_runtime_config(db)

    assert runtime.provider_type == "openai_compatible"
    assert runtime.provider_base_url == "https://api.deepseek.com/v1"
    assert runtime.provider_api_key == "sk-test"
    assert runtime.chat_model == "deepseek-chat"
    assert runtime.embedding_model == "text-embedding-3-small"
    assert runtime.vision_model == "qwen-vl-plus"
    assert runtime.sse_done_mode == "async"
    assert runtime.usage_source == "actual"


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
