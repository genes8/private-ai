from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agents.graph import build_graph
from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.config import settings
from app.services.app_config_store import load_app_config

_DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_DEFAULT_VISION_MODEL = "qwen2.5vl:7b"


@dataclass(frozen=True)
class RuntimeConfig:
    generation_model: str
    generation_fallback_model: str
    embedding_model: str
    reranker_enabled: bool
    reranker_model: str
    retrieval_k: int
    score_floor: float
    chunk_size: int
    chunk_overlap: int
    vision_model: str


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
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
    generation_model = str(cfg.get("generation_model", settings.ollama_model))
    return RuntimeConfig(
        generation_model=generation_model,
        generation_fallback_model=str(
            cfg.get("generation_fallback_model", generation_model)
        ),
        embedding_model=str(cfg.get("embedding_model", settings.embedding_model)),
        reranker_enabled=_coerce_bool(cfg.get("reranker_enabled"), True),
        reranker_model=str(cfg.get("reranker_model", _DEFAULT_RERANKER_MODEL)),
        retrieval_k=_coerce_int(cfg.get("retrieval_k"), 6),
        score_floor=_coerce_float(cfg.get("score_floor"), 0.45),
        chunk_size=_coerce_int(cfg.get("chunk_size"), 800),
        chunk_overlap=_coerce_int(cfg.get("chunk_overlap"), 150),
        vision_model=str(cfg.get("vision_model", _DEFAULT_VISION_MODEL)),
    )


def build_runtime_components(db: Session) -> tuple[RuntimeConfig, HybridRetriever, Reranker, Any]:
    """Build the runtime retriever, reranker, and compiled graph from persisted config."""
    runtime = load_runtime_config(db)
    retriever = HybridRetriever(
        qdrant_url=settings.qdrant_url,
        collection="documents",
        ollama_url=settings.ollama_url,
        embedding_model=runtime.embedding_model,
    )
    reranker = Reranker(model_name=runtime.reranker_model, enabled=runtime.reranker_enabled)
    graph = build_graph(
        retriever=retriever,
        reranker=reranker,
        ollama_url=settings.ollama_url,
        ollama_model=runtime.generation_model,
        retrieval_top_k=runtime.retrieval_k,
    )
    return runtime, retriever, reranker, graph
