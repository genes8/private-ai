"""Settings patch business logic extracted from the HTTP handler.

Three-stage pipeline:
  normalize  → expand mode shorthands, snapshot prev state, derive effective values
  probe      → I/O: verify Ollama / cloud provider reachability, sanitize stale model slots
  collect    → validate each individual field, build the DB updates dict
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

import httpx
import structlog
from pydantic import BaseModel
from qdrant_client import QdrantClient as _QdrantClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Document
from app.services.app_config_store import load_app_config
from app.services.provider_settings import (
    expand_provider_mode,
    probe_cloud_embeddings,
    resolve_provider_config,
    sanitize_ollama_role_models,
    validate_hybrid_embedding,
)
from app.services.runtime_config import expected_vector_size
from app.services.settings_exceptions import EmbeddingDimensionConflict, SettingsValidationError
from app.security.url_validator import validate_provider_url
from observability.cost_tracker import CostTracker

logger = structlog.get_logger(__name__)

_DEFAULT_VISION_MODEL = "qwen2.5vl:7b"


# ---------------------------------------------------------------------------
# Request model (lives here so the service and route share the same type)
# ---------------------------------------------------------------------------

class PatchSettingsRequest(BaseModel):
    generationModel: str | None = None
    generationFallback: str | None = None
    embeddingModel: str | None = None
    visionModel: str | None = None
    rerankerEnabled: bool | None = None
    rerankerModel: str | None = None
    retrievalK: int | None = None
    scoreFloor: float | None = None
    chunkSize: int | None = None
    chunkOverlap: int | None = None
    ssoOnly: bool | None = None
    sessionHours: int | None = None
    auditRetentionDays: int | None = None
    redactPII: bool | None = None
    dailyCeilingUsd: float | None = None
    monthlyCeilingUsd: float | None = None
    # Inference provider fields
    providerType: str | None = None
    providerBaseUrl: str | None = None
    providerApiKey: str | None = None
    providerChatModel: str | None = None
    providerEmbeddingModel: str | None = None
    providerVisionModel: str | None = None
    sseDoneMode: str | None = None
    providerCustomModels: list[str] | None = None
    embeddingSource: str | None = None   # "ollama" | "provider"
    providerMode: str | None = None      # "local" | "hybrid" | "cloud"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def validate_model_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise SettingsValidationError(f"{field_name} cannot be empty")
    if len(normalized) > 200:
        raise SettingsValidationError(f"{field_name} is too long")
    return normalized


def fetch_ollama_model_names() -> set[str]:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SettingsValidationError("Unable to verify model availability") from exc

    data = resp.json()
    models = data.get("models", [])
    names = {
        str(model.get("name", "")).strip()
        for model in models
        if isinstance(model, dict) and model.get("name")
    }
    return {name for name in names if name}


def _validate_ollama_model_exists(value: str, field_name: str, available_models: set[str]) -> str:
    normalized = validate_model_identifier(value, field_name)
    if normalized not in available_models:
        raise SettingsValidationError(f"{field_name} is not available in Ollama")
    return normalized


def _validate_embedding_model_dimension(model: str) -> None:
    """Raise 409 if the new embedding model's known dimension differs from the collection's."""
    expected = expected_vector_size(model)
    if expected is None:
        return
    try:
        info = _QdrantClient(url=settings.qdrant_url).get_collection("documents")
        vectors_cfg = info.config.params.vectors
        actual: int = (
            next(iter(vectors_cfg.values())).size  # type: ignore[union-attr]
            if isinstance(vectors_cfg, dict)
            else vectors_cfg.size  # type: ignore[union-attr]
        )
        if actual != expected:
            raise EmbeddingDimensionConflict(
                f"Embedding model '{model}' requires vector size {expected} but "
                f"the Qdrant collection currently has size {actual}. "
                "Drop and recreate the collection before switching embedding models."
            )
    except EmbeddingDimensionConflict:
        raise
    except Exception:  # noqa: S110
        pass  # Qdrant unreachable is non-fatal — startup guard will catch it


# ---------------------------------------------------------------------------
# Stage 1 — Normalize
# ---------------------------------------------------------------------------

def normalize_patch_request(
    body: PatchSettingsRequest,
    current_config: dict[str, Any],
) -> tuple[PatchSettingsRequest, dict[str, Any], str, str, str, str]:
    """Expand mode shorthands and derive canonical effective values.

    Returns:
        (body, pre_updates, effective_provider, effective_embedding_source,
         prev_embedding_model, prev_embedding_source)
    """
    pre_updates: dict[str, Any] = {}

    if body.providerMode is not None:
        patch = expand_provider_mode(body.providerMode, body.providerBaseUrl)
        pre_updates.update(patch.pre_updates)
        body = body.model_copy(update=patch.body_overrides)

    prev_embedding_model = str(current_config.get("embedding_model", settings.embedding_model))
    prev_embedding_source = resolve_provider_config(current_config).embedding_source

    effective_provider = str(body.providerType or current_config.get("provider_type", "ollama"))
    _eff_embed_default = "provider" if effective_provider == "openai_compatible" else "ollama"
    effective_embedding_source = str(
        body.embeddingSource or current_config.get("embedding_source", _eff_embed_default)
    )

    return body, pre_updates, effective_provider, effective_embedding_source, prev_embedding_model, prev_embedding_source


# ---------------------------------------------------------------------------
# Stage 2 — Probe
# ---------------------------------------------------------------------------

def probe_provider_prerequisites(
    body: PatchSettingsRequest,
    current_config: dict[str, Any],
    effective_provider: str,
    effective_embedding_source: str,
) -> tuple[dict[str, Any], PatchSettingsRequest]:
    """Probe external services and sanitize stale model slots.

    Returns:
        (probe_updates, body)  — body may have embeddingModel updated to a fallback
    """
    probe_updates: dict[str, Any] = {}

    if effective_provider == "openai_compatible" and effective_embedding_source == "ollama":
        try:
            available_ollama = fetch_ollama_model_names()
        except SettingsValidationError:
            raise SettingsValidationError(
                "Hybrid mode requires local Ollama for embeddings but Ollama is not reachable. "
                "Start Ollama first, then switch to Hybrid."
            )
        fallback = validate_hybrid_embedding(
            available_ollama=available_ollama,
            current_embedding_model=str(
                current_config.get("embedding_model", settings.embedding_model)
            ),
            requested_embedding_model=body.embeddingModel,
            default_embedding_model=settings.embedding_model,
        )
        if fallback is not None:
            body = body.model_copy(update={"embeddingModel": fallback})
        if body.providerMode is not None:
            probe_updates.update(
                sanitize_ollama_role_models(
                    "hybrid",
                    current_config,
                    available_ollama,
                    default_generation_model=settings.ollama_model,
                    default_embedding_model=settings.embedding_model,
                    default_vision_model=_DEFAULT_VISION_MODEL,
                )
            )

    if body.providerMode is not None and effective_provider == "ollama":
        try:
            available_for_local = fetch_ollama_model_names()
        except SettingsValidationError:
            raise SettingsValidationError(
                "Local mode requires Ollama but it is not reachable. "
                "Start Ollama first, then switch to Local."
            )
        probe_updates.update(
            sanitize_ollama_role_models(
                "local",
                current_config,
                available_for_local,
                default_generation_model=settings.ollama_model,
                default_embedding_model=settings.embedding_model,
                default_vision_model=_DEFAULT_VISION_MODEL,
            )
        )

    if effective_provider == "openai_compatible" and effective_embedding_source == "provider":
        probe_cloud_embeddings(
            base_url=body.providerBaseUrl or str(current_config.get("provider_base_url", "")),
            api_key=body.providerApiKey or str(current_config.get("provider_api_key", "")),
            embedding_model=(
                body.providerEmbeddingModel
                or body.embeddingModel
                or str(current_config.get("provider_embedding_model", ""))
                or str(current_config.get("embedding_model", settings.embedding_model))
            ),
        )

    return probe_updates, body


# ---------------------------------------------------------------------------
# Stage 3 — Collect field updates
# ---------------------------------------------------------------------------

def collect_field_updates(
    body: PatchSettingsRequest,
    effective_provider: str,
    current_config: dict[str, Any],
) -> dict[str, Any]:
    """Validate each individual request field and build the DB updates dict."""
    updates: dict[str, Any] = {}

    if effective_provider == "ollama":
        requested_ollama_models = any(
            v is not None
            for v in (body.generationModel, body.generationFallback, body.embeddingModel, body.visionModel)
        )
        available_ollama = fetch_ollama_model_names() if requested_ollama_models else set()
        if body.generationModel is not None:
            updates["generation_model"] = _validate_ollama_model_exists(
                body.generationModel, "generationModel", available_ollama
            )
        if body.generationFallback is not None:
            updates["generation_fallback_model"] = _validate_ollama_model_exists(
                body.generationFallback, "generationFallback", available_ollama
            )
        if body.embeddingModel is not None:
            updates["embedding_model"] = _validate_ollama_model_exists(
                body.embeddingModel, "embeddingModel", available_ollama
            )
            _validate_embedding_model_dimension(body.embeddingModel)
        if body.visionModel is not None:
            updates["vision_model"] = _validate_ollama_model_exists(
                body.visionModel, "visionModel", available_ollama
            )
    else:
        if body.generationModel is not None:
            generation_model = validate_model_identifier(body.generationModel, "generationModel")
            updates["generation_model"] = generation_model
            if body.providerChatModel is None:
                updates["provider_chat_model"] = generation_model
        if body.generationFallback is not None:
            updates["generation_fallback_model"] = validate_model_identifier(
                body.generationFallback, "generationFallback"
            )
        if body.embeddingModel is not None:
            embedding_model = validate_model_identifier(body.embeddingModel, "embeddingModel")
            updates["embedding_model"] = embedding_model
            if body.providerEmbeddingModel is None:
                updates["provider_embedding_model"] = embedding_model
            _validate_embedding_model_dimension(body.embeddingModel)
        if body.visionModel is not None:
            vision_model = validate_model_identifier(body.visionModel, "visionModel")
            updates["vision_model"] = vision_model
            if body.providerVisionModel is None:
                updates["provider_vision_model"] = vision_model

    if body.rerankerEnabled is not None:
        updates["reranker_enabled"] = body.rerankerEnabled
    if body.rerankerModel is not None:
        updates["reranker_model"] = validate_model_identifier(body.rerankerModel, "rerankerModel")
    if body.retrievalK is not None:
        if body.retrievalK < 1 or body.retrievalK > 32:
            raise SettingsValidationError("retrievalK must be between 1 and 32")
        updates["retrieval_k"] = body.retrievalK
    if body.scoreFloor is not None:
        if body.scoreFloor < 0 or body.scoreFloor > 1:
            raise SettingsValidationError("scoreFloor must be between 0 and 1")
        updates["score_floor"] = body.scoreFloor
    if body.chunkSize is not None:
        if body.chunkSize < 128 or body.chunkSize > 2048:
            raise SettingsValidationError("chunkSize must be between 128 and 2048")
        current_overlap = int(current_config.get("chunk_overlap", 150))
        if body.chunkOverlap is None and current_overlap >= body.chunkSize:
            raise SettingsValidationError("chunkSize must be larger than chunkOverlap")
        updates["chunk_size"] = body.chunkSize
    if body.chunkOverlap is not None:
        if body.chunkOverlap < 0 or body.chunkOverlap > 512:
            raise SettingsValidationError("chunkOverlap must be between 0 and 512")
        current_chunk_size = int(current_config.get("chunk_size", 800))
        effective_chunk_size = body.chunkSize if body.chunkSize is not None else current_chunk_size
        if body.chunkOverlap >= effective_chunk_size:
            raise SettingsValidationError("chunkOverlap must be smaller than chunkSize")
        updates["chunk_overlap"] = body.chunkOverlap
    if body.ssoOnly is not None:
        updates["sso_only"] = body.ssoOnly
    if body.sessionHours is not None:
        if body.sessionHours < 1 or body.sessionHours > 720:
            raise SettingsValidationError("sessionHours must be between 1 and 720")
        updates["session_hours"] = body.sessionHours
    if body.auditRetentionDays is not None:
        if body.auditRetentionDays < 30 or body.auditRetentionDays > 3650:
            raise SettingsValidationError("auditRetentionDays must be between 30 and 3650")
        updates["audit_retention_days"] = body.auditRetentionDays
    if body.redactPII is not None:
        updates["redact_pii"] = body.redactPII
    if body.dailyCeilingUsd is not None:
        if body.dailyCeilingUsd < 1 or body.dailyCeilingUsd > 10000:
            raise SettingsValidationError("dailyCeilingUsd must be between 1 and 10000")
        updates["daily_ceiling_usd"] = body.dailyCeilingUsd
    if body.monthlyCeilingUsd is not None:
        if body.monthlyCeilingUsd < 30 or body.monthlyCeilingUsd > 300000:
            raise SettingsValidationError("monthlyCeilingUsd must be between 30 and 300000")
        updates["monthly_ceiling_usd"] = body.monthlyCeilingUsd

    if body.providerType is not None:
        if body.providerType not in {"ollama", "openai_compatible"}:
            raise SettingsValidationError("providerType must be ollama or openai_compatible")
        updates["provider_type"] = body.providerType
    if body.providerBaseUrl is not None:
        clean_url, resolved_ip = validate_provider_url(body.providerBaseUrl)
        updates["provider_base_url"] = clean_url
        updates["provider_resolved_ip"] = resolved_ip  # pin against DNS rebinding; use as connection target
    if body.providerApiKey is not None:
        updates["provider_api_key"] = body.providerApiKey
    if body.providerChatModel is not None:
        provider_chat_model = validate_model_identifier(body.providerChatModel, "providerChatModel")
        updates["provider_chat_model"] = provider_chat_model
        if effective_provider == "openai_compatible" and body.generationModel is None:
            updates["generation_model"] = provider_chat_model
    if body.providerEmbeddingModel is not None:
        provider_embedding_model = validate_model_identifier(
            body.providerEmbeddingModel, "providerEmbeddingModel"
        )
        updates["provider_embedding_model"] = provider_embedding_model
        if effective_provider == "openai_compatible" and body.embeddingModel is None:
            updates["embedding_model"] = provider_embedding_model
        _validate_embedding_model_dimension(body.providerEmbeddingModel)
    if body.providerVisionModel is not None:
        provider_vision_model = validate_model_identifier(
            body.providerVisionModel, "providerVisionModel"
        )
        updates["provider_vision_model"] = provider_vision_model
        if effective_provider == "openai_compatible" and body.visionModel is None:
            updates["vision_model"] = provider_vision_model
    if body.sseDoneMode is not None:
        if body.sseDoneMode not in {"strict", "async"}:
            raise SettingsValidationError("sseDoneMode must be strict or async")
        updates["sse_done_mode"] = body.sseDoneMode
    if body.providerCustomModels is not None:
        if len(body.providerCustomModels) > 50:
            raise SettingsValidationError("Too many custom models (max 50)")
        updates["custom_provider_models"] = [
            validate_model_identifier(m, "providerCustomModels")
            for m in body.providerCustomModels
        ]
    if body.embeddingSource is not None:
        if body.embeddingSource not in {"ollama", "provider"}:
            raise SettingsValidationError("embeddingSource must be ollama or provider")
        updates["embedding_source"] = body.embeddingSource

    return updates


# ---------------------------------------------------------------------------
# Settings serialization — pure business logic; no HTTP concerns
# ---------------------------------------------------------------------------

_SETTINGS_LIVE_TTL_SECONDS = 60.0
_settings_live_cache: dict[str, Any] = {
    "expires_at": 0.0,
    "today_cost": 0.0,
    "available_ollama_models": [],
    "doc_count": 0,
    "available_provider_models": [],
}
_settings_live_cache_lock = threading.Lock()


def _fetch_provider_model_names(base_url: str, api_key: str) -> list[str]:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
        data = resp.json()
        models = data.get("data", [])
        return sorted({str(m.get("id", "")) for m in models if isinstance(m, dict) and m.get("id")})
    except Exception:
        return []


def _get_settings_live_metadata(db: Session) -> tuple[float, list[str], int, list[str]]:
    now = time.monotonic()
    with _settings_live_cache_lock:
        if now < float(_settings_live_cache["expires_at"]):
            return (
                float(_settings_live_cache["today_cost"]),
                list(_settings_live_cache["available_ollama_models"]),
                int(_settings_live_cache["doc_count"]),
                list(_settings_live_cache["available_provider_models"]),
            )

    today_cost = CostTracker(settings.cost_per_1k_tokens).get_stats(db, days=1)["total_cost_usd"]
    try:
        available_ollama_models = sorted(fetch_ollama_model_names())
    except SettingsValidationError:
        available_ollama_models = []
    doc_count = db.query(func.count(Document.id)).scalar() or 0

    db_config = load_app_config(db)
    provider_type = resolve_provider_config(db_config).provider_type
    available_provider_models: list[str] = []
    if provider_type == "openai_compatible":
        base_url = str(db_config.get("provider_base_url", ""))
        api_key = str(db_config.get("provider_api_key", ""))
        if base_url and api_key:
            available_provider_models = _fetch_provider_model_names(base_url, api_key)

    with _settings_live_cache_lock:
        _settings_live_cache.update(
            {
                "expires_at": now + _SETTINGS_LIVE_TTL_SECONDS,
                "today_cost": today_cost,
                "available_ollama_models": available_ollama_models,
                "doc_count": doc_count,
                "available_provider_models": available_provider_models,
            }
        )
    return (
        float(today_cost),
        list(available_ollama_models),
        int(doc_count),
        list(available_provider_models),
    )


def serialize_settings(db: Session) -> dict[str, Any]:
    """Build the complete settings response dict. No HTTP concerns — pure data assembly."""
    db_overrides = load_app_config(db)

    def _val(key: str, default: Any) -> Any:
        return db_overrides.get(key, default)

    today_cost, available_ollama_models, doc_count, available_provider_models = (
        _get_settings_live_metadata(db)
    )
    current_ollama_models = {
        str(_val("generation_model", settings.ollama_model)),
        str(_val("generation_fallback_model", settings.ollama_model)),
        str(_val("embedding_model", settings.embedding_model)),
        str(_val("vision_model", "qwen2.5vl:7b")),
    }
    custom_provider_models: list[str] = []
    try:
        raw_custom = _val("custom_provider_models", "[]")
        parsed = json.loads(raw_custom) if isinstance(raw_custom, str) else raw_custom
        custom_provider_models = [str(m) for m in parsed if isinstance(m, str)]
    except (json.JSONDecodeError, TypeError, ValueError):
        custom_provider_models = []
    all_provider_models = sorted(set(available_provider_models) | set(custom_provider_models))
    provider_api_key_raw = _val("provider_api_key", "")

    _prov = resolve_provider_config(db_overrides)
    provider_type = _prov.provider_type
    embedding_source = _prov.embedding_source
    provider_mode = _prov.provider_mode

    return {
        "generationModel": _val("generation_model", settings.ollama_model),
        "generationFallback": _val("generation_fallback_model", settings.ollama_model),
        "embeddingModel": _val("embedding_model", settings.embedding_model),
        "visionModel": _val("vision_model", "qwen2.5vl:7b"),
        "provider": {
            "type": provider_type,
            "baseUrl": _val("provider_base_url", settings.ollama_url),
            "apiKeyConfigured": bool(provider_api_key_raw),
            "chatModel": (
                _val("generation_model", settings.ollama_model)
                if provider_type == "ollama"
                else _val("provider_chat_model", _val("generation_model", settings.ollama_model))
            ),
            "embeddingModel": (
                _val("embedding_model", settings.embedding_model)
                if embedding_source == "ollama"
                else _val(
                    "provider_embedding_model",
                    _val("embedding_model", settings.embedding_model),
                )
            ),
            "visionModel": (
                _val("vision_model", "qwen2.5vl:7b")
                if embedding_source == "ollama"
                else _val("provider_vision_model", "qwen2.5vl:7b")
            ),
            "embeddingSource": embedding_source,
            "providerMode": provider_mode,
        },
        "sseDoneMode": _val("sse_done_mode", "strict"),
        "availableModels": {
            "ollama": sorted(set(available_ollama_models) | current_ollama_models),
            "provider": all_provider_models,
            "reranker": [
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "bge-reranker-v2",
            ],
            "customProvider": custom_provider_models,
        },
        "reranker": {
            "enabled": _val("reranker_enabled", True),
            "model": _val("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        },
        "retrieval": {
            "k": _val("retrieval_k", 6),
            "scoreFloor": _val("score_floor", 0.45),
            "chunkSize": _val("chunk_size", 800),
            "chunkOverlap": _val("chunk_overlap", 150),
        },
        "sources": [
            {
                "id": "src-1",
                "kind": "watch",
                "label": "data/raw",
                "detail": "Local filesystem watch",
                "docCount": doc_count,
                "syncedAt": None,
                "status": "ok",
            },
        ],
        "security": {
            "ssoOnly": _val("sso_only", False),
            "sessionHours": _val("session_hours", 24),
            "auditRetentionDays": _val("audit_retention_days", settings.audit_log_retention_days),
            "redactPII": _val("redact_pii", False),
        },
        "cost": {
            "dailyCeilingUsd": _val("daily_ceiling_usd", 50),
            "monthlyCeilingUsd": _val("monthly_ceiling_usd", 500),
            "todayUsd": today_cost,
        },
    }


def invalidate_live_cache() -> None:
    """Force the next serialize_settings() call to re-fetch live data."""
    with _settings_live_cache_lock:
        _settings_live_cache["expires_at"] = 0.0
