from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agents.graph import build_graph
from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.config import settings
from app.services.app_config_store import load_app_config
from app.services.provider_clients import (
    EmbeddingClient,
    OllamaProvider,
    OpenAICompatibleProvider,
)

_DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_DEFAULT_VISION_MODEL = "qwen2.5vl:7b"

# Known embedding dimensions keyed by model name (lower-case).
_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def expected_vector_size(model: str) -> int | None:
    """Return the known vector dimension for a model name, or None if unknown."""
    return _EMBEDDING_DIMENSIONS.get(model.strip().lower())


@dataclass(frozen=True)
class RuntimeConfig:
    provider_type: str
    provider_base_url: str
    provider_api_key: str | None
    generation_model: str
    generation_fallback_model: str
    chat_model: str
    embedding_model: str
    vision_model: str
    reranker_enabled: bool
    reranker_model: str
    retrieval_k: int
    score_floor: float
    chunk_size: int
    chunk_overlap: int
    sse_done_mode: str
    usage_source: str


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_runtime_config(db: Session) -> RuntimeConfig:
    """Load persisted settings, falling back to environment defaults."""
    cfg = load_app_config(db)

    provider_type = str(cfg.get("provider_type", "ollama"))
    if provider_type not in {"ollama", "openai_compatible"}:
        provider_type = "ollama"

    generation_model = str(cfg.get("generation_model", settings.ollama_model))
    provider_chat_model = str(cfg.get("provider_chat_model", generation_model))
    provider_embedding_model = str(cfg.get("provider_embedding_model", settings.embedding_model))
    provider_vision_model = str(cfg.get("provider_vision_model", _DEFAULT_VISION_MODEL))
    provider_base_url = str(
        cfg.get(
            "provider_base_url",
            settings.ollama_url if provider_type == "ollama" else "https://api.openai.com/v1",
        )
    )

    sse_done_mode = str(cfg.get("sse_done_mode", "strict"))
    if sse_done_mode not in {"strict", "async"}:
        sse_done_mode = "strict"

    return RuntimeConfig(
        provider_type=provider_type,
        provider_base_url=provider_base_url.rstrip("/"),
        provider_api_key=cfg.get("provider_api_key"),
        generation_model=generation_model,
        generation_fallback_model=str(cfg.get("generation_fallback_model", generation_model)),
        chat_model=provider_chat_model,
        embedding_model=provider_embedding_model,
        vision_model=provider_vision_model,
        reranker_enabled=_coerce_bool(cfg.get("reranker_enabled"), True),
        reranker_model=str(cfg.get("reranker_model", _DEFAULT_RERANKER_MODEL)),
        retrieval_k=_coerce_int(cfg.get("retrieval_k"), 6),
        score_floor=_coerce_float(cfg.get("score_floor"), 0.45),
        chunk_size=_coerce_int(cfg.get("chunk_size"), 800),
        chunk_overlap=_coerce_int(cfg.get("chunk_overlap"), 150),
        sse_done_mode=sse_done_mode,
        usage_source="actual" if provider_type == "openai_compatible" else "estimated",
    )


def build_provider(runtime: RuntimeConfig) -> OllamaProvider | OpenAICompatibleProvider:
    """Instantiate the configured inference provider."""
    if runtime.provider_type == "openai_compatible":
        if not runtime.provider_api_key:
            raise RuntimeError("OpenAI-compatible provider requires an API key")
        return OpenAICompatibleProvider(
            base_url=runtime.provider_base_url,
            api_key=runtime.provider_api_key,
            chat_model=runtime.chat_model,
            embedding_model=runtime.embedding_model,
            vision_model=runtime.vision_model,
        )
    return OllamaProvider(
        base_url=runtime.provider_base_url,
        chat_model=runtime.chat_model,
        embedding_model=runtime.embedding_model,
        vision_model=runtime.vision_model,
    )


def build_runtime_components(db: Session) -> tuple[RuntimeConfig, HybridRetriever, Reranker, Any]:
    """Build the runtime retriever, reranker, and compiled graph from persisted config."""
    runtime = load_runtime_config(db)
    provider = build_provider(runtime)
    retriever = HybridRetriever(
        qdrant_url=settings.qdrant_url,
        collection="documents",
        embedding_model=runtime.embedding_model,
        embedding_client=provider,
    )
    reranker = Reranker(model_name=runtime.reranker_model, enabled=runtime.reranker_enabled)
    graph = build_graph(
        retriever=retriever,
        reranker=reranker,
        chat_client=provider,
        ollama_url=runtime.provider_base_url,
        ollama_model=runtime.chat_model,
        retrieval_top_k=runtime.retrieval_k,
        rerank_threshold=runtime.score_floor,
    )
    return runtime, retriever, reranker, graph
