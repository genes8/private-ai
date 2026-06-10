from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agents.graph import build_graph
from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.config import settings
from app.security.url_validator import validate_provider_url
from app.services.app_config_store import load_app_config
from app.services.provider_clients import (
    OllamaProvider,
    OpenAICompatibleProvider,
)
from app.services.provider_settings import (
    effective_provider_base_url,
    resolve_provider_config,
)

_DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_DEFAULT_VISION_MODEL = "qwen3.5:9b"

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
    provider_resolved_ip: str | None
    provider_api_key: str | None
    embedding_source: str  # "ollama" | "provider"
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
    blocked_terms: list[str]

    @property
    def provider_mode(self) -> str:
        if self.provider_type == "ollama":
            return "local"
        return "hybrid" if self.embedding_source == "ollama" else "cloud"


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


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def _provider_resolved_ip(
    *,
    provider_type: str,
    provider_base_url: str,
    configured_ip: Any,
) -> str | None:
    if provider_type != "openai_compatible":
        return None
    if configured_ip:
        return str(configured_ip).strip()
    _clean_url, resolved_ip = validate_provider_url(provider_base_url)
    return resolved_ip


def load_runtime_config(db: Session) -> RuntimeConfig:
    """Load persisted settings, falling back to environment defaults."""
    cfg = load_app_config(db)

    _res = resolve_provider_config(cfg)
    provider_type = _res.provider_type
    embedding_source = _res.embedding_source

    generation_model = str(cfg.get("generation_model", settings.ollama_model))
    provider_chat_model = str(cfg.get("provider_chat_model", generation_model))
    # For local Ollama, chat_model is always generation_model — avoids a stale provider_chat_model
    # left over from a previous cloud session overriding the local model selection.
    effective_chat_model = generation_model if provider_type == "ollama" else provider_chat_model
    embedding_model_base = str(cfg.get("embedding_model", settings.embedding_model))
    vision_model_base = str(cfg.get("vision_model", _DEFAULT_VISION_MODEL))
    provider_embedding_model = str(cfg.get("provider_embedding_model", settings.embedding_model))
    provider_vision_model = str(cfg.get("provider_vision_model", _DEFAULT_VISION_MODEL))
    provider_base_url = effective_provider_base_url(provider_type, cfg)

    sse_done_mode = str(cfg.get("sse_done_mode", "strict"))
    if sse_done_mode not in {"strict", "async"}:
        sse_done_mode = "strict"

    # For local/hybrid modes embeddings run on Ollama — use the Ollama model names, not the cloud
    # provider models that may have been left in provider_embedding_model / provider_vision_model
    # from a previous cloud session.
    effective_embedding_model = (
        embedding_model_base if embedding_source == "ollama" else provider_embedding_model
    )
    effective_vision_model = (
        vision_model_base if embedding_source == "ollama" else provider_vision_model
    )

    return RuntimeConfig(
        provider_type=provider_type,
        provider_base_url=provider_base_url,
        provider_resolved_ip=_provider_resolved_ip(
            provider_type=provider_type,
            provider_base_url=provider_base_url,
            configured_ip=cfg.get("provider_resolved_ip"),
        ),
        provider_api_key=cfg.get("provider_api_key"),
        embedding_source=embedding_source,
        generation_model=generation_model,
        generation_fallback_model=str(cfg.get("generation_fallback_model", generation_model)),
        chat_model=effective_chat_model,
        embedding_model=effective_embedding_model,
        vision_model=effective_vision_model,
        reranker_enabled=_coerce_bool(cfg.get("reranker_enabled"), True),
        reranker_model=str(cfg.get("reranker_model", _DEFAULT_RERANKER_MODEL)),
        retrieval_k=_coerce_int(cfg.get("retrieval_k"), 6),
        score_floor=_coerce_float(cfg.get("score_floor"), 0.45),
        chunk_size=_coerce_int(cfg.get("chunk_size"), 800),
        chunk_overlap=_coerce_int(cfg.get("chunk_overlap"), 150),
        sse_done_mode=sse_done_mode,
        usage_source="actual" if provider_type == "openai_compatible" else "estimated",
        blocked_terms=_coerce_string_list(cfg.get("blocked_terms")),
    )


def build_provider(runtime: RuntimeConfig) -> OllamaProvider | OpenAICompatibleProvider:
    """Instantiate the chat inference provider."""
    if runtime.provider_type == "openai_compatible":
        if not runtime.provider_api_key:
            raise RuntimeError("OpenAI-compatible provider requires an API key")
        return OpenAICompatibleProvider(
            base_url=runtime.provider_base_url,
            resolved_ip=runtime.provider_resolved_ip,
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


def _build_local_ollama_provider(runtime: RuntimeConfig) -> OllamaProvider:
    """OllamaProvider pointed at the local Ollama URL (never the cloud provider URL)."""
    return OllamaProvider(
        base_url=settings.ollama_url,
        chat_model=runtime.chat_model,
        embedding_model=runtime.embedding_model,
        vision_model=runtime.vision_model,
    )


def build_embedding_provider(runtime: RuntimeConfig) -> OllamaProvider | OpenAICompatibleProvider:
    """Return the provider for embed_query / embed_documents calls.

    In hybrid mode embeddings always use local Ollama — NOT runtime.provider_base_url.
    """
    if runtime.embedding_source == "provider":
        return build_provider(runtime)
    return _build_local_ollama_provider(runtime)


def build_vision_provider(runtime: RuntimeConfig) -> OllamaProvider | OpenAICompatibleProvider:
    """Return the provider for describe_image / OCR calls.

    In hybrid and local modes vision uses local Ollama (vision_model is an Ollama-only model).
    """
    if runtime.embedding_source == "provider":
        return build_provider(runtime)
    return _build_local_ollama_provider(runtime)


def build_runtime_components(db: Session) -> tuple[RuntimeConfig, HybridRetriever, Reranker, Any]:
    """Build the runtime retriever, reranker, and compiled graph from persisted config."""
    runtime = load_runtime_config(db)
    chat_provider = build_provider(runtime)
    embedding_provider = build_embedding_provider(runtime)
    retriever = HybridRetriever(
        qdrant_url=settings.qdrant_url,
        collection="documents",
        embedding_model=runtime.embedding_model,
        embedding_client=embedding_provider,
    )
    reranker = Reranker(model_name=runtime.reranker_model, enabled=runtime.reranker_enabled)
    graph = build_graph(
        retriever=retriever,
        reranker=reranker,
        chat_client=chat_provider,
        ollama_url=runtime.provider_base_url,
        ollama_model=runtime.chat_model,
        retrieval_top_k=runtime.retrieval_k,
        rerank_threshold=runtime.score_floor,
        blocked_terms=runtime.blocked_terms,
    )
    return runtime, retriever, reranker, graph
