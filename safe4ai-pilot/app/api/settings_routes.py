from __future__ import annotations

import json
import threading
import time
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.middleware import require_role
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import Document, User
from app.services.app_config_store import load_app_config, upsert_app_config
from app.security.url_validator import validate_provider_url
from app.services.provider_settings import resolve_provider_config
from app.services.runtime_config import build_runtime_components
from app.services import settings_service as _svc
from app.services.settings_service import (
    PatchSettingsRequest,
    collect_field_updates,
    normalize_patch_request,
    probe_provider_prerequisites,
)
from observability.cost_tracker import CostTracker

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["settings"])

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
        available_ollama_models = sorted(_svc.fetch_ollama_model_names())
    except HTTPException:
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


def _serialize_settings(db: Session) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings")
@limiter.limit("100/minute")
def get_settings(
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Return current application settings, mixing env vars with DB overrides."""
    return _serialize_settings(db)


@router.patch("/settings", status_code=200)
def patch_settings(
    request: Request,
    body: PatchSettingsRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Update mutable application settings stored in the DB."""
    current_config = load_app_config(db)

    # Stage 1: expand mode shorthands, snapshot prev state, derive effective values
    body, pre_updates, effective_provider, effective_embedding_source, prev_embedding_model, prev_embedding_source = (
        normalize_patch_request(body, current_config)
    )
    updates: dict[str, Any] = dict(pre_updates)

    # Stage 2: probe Ollama / cloud reachability, sanitize stale model slots
    probe_updates, body = probe_provider_prerequisites(
        body, current_config, effective_provider, effective_embedding_source
    )
    updates.update(probe_updates)

    # Stage 3: validate each field and collect DB updates
    updates.update(collect_field_updates(body, effective_provider, current_config))

    # Require API key when switching to openai_compatible
    effective_key = body.providerApiKey or current_config.get("provider_api_key")
    if effective_provider == "openai_compatible" and not effective_key:
        raise HTTPException(
            status_code=422, detail="providerApiKey is required for openai_compatible"
        )

    # Enforce provider/embedding_source invariant: resolve canonical values and persist them.
    next_config = {**current_config, **updates}
    _next = resolve_provider_config(next_config)
    updates["provider_type"] = _next.provider_type
    updates["embedding_source"] = _next.embedding_source

    upsert_app_config(db, updates, commit=False)
    try:
        _runtime, retriever, reranker, graph = build_runtime_components(db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"Configuration is invalid and was not saved: {exc}",
        ) from exc
    db.commit()
    request.app.state.retriever = retriever
    request.app.state.reranker = reranker
    request.app.state.graph = graph
    with _settings_live_cache_lock:
        _settings_live_cache["expires_at"] = 0.0
    logger.info("settings_updated", keys=list(updates.keys()))
    result = _serialize_settings(db)
    result["reindexRequired"] = (
        updates.get("embedding_model", prev_embedding_model) != prev_embedding_model
        or _next.embedding_source != prev_embedding_source
    )
    return result


@router.post("/settings/provider/test", status_code=200)
def test_provider_connection(
    request: Request,
    body: PatchSettingsRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict[str, str]:
    """Validate provider credentials with a lightweight connectivity check."""
    from app.services.provider_clients import OpenAICompatibleProvider  # noqa: F401

    provider_type = body.providerType or str(load_app_config(db).get("provider_type", "ollama"))
    base_url = body.providerBaseUrl or str(
        load_app_config(db).get("provider_base_url", settings.ollama_url)
    )
    api_key = body.providerApiKey or load_app_config(db).get("provider_api_key", "")

    if provider_type == "openai_compatible":
        if not api_key:
            raise HTTPException(
                status_code=422, detail="providerApiKey is required for openai_compatible"
            )
        clean_url, resolved_ip = validate_provider_url(base_url)
        parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(clean_url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        transport = httpx.HTTPTransport(local_address=None)

        class _PinnedTransport(httpx.HTTPTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                request.url = request.url.copy_with(host=resolved_ip)
                request.headers["host"] = parsed.hostname or resolved_ip
                return super().handle_request(request)

        try:
            with httpx.Client(transport=_PinnedTransport(), timeout=10.0) as client:
                resp = client.get(
                    f"{clean_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code >= 400:
                    detail = (
                        "Invalid credentials — check your API key"
                        if resp.status_code in {401, 403}
                        else "Provider returned an error"
                    )
                    raise HTTPException(status_code=503, detail=detail)
        except HTTPException:
            raise
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="Provider connection failed") from None
        except Exception:
            raise HTTPException(status_code=503, detail="Provider connection failed") from None
    else:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{base_url.rstrip('/')}/api/tags")
                if resp.status_code >= 400:
                    raise HTTPException(status_code=503, detail="Ollama not reachable")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"Ollama connection failed: {exc}"
            ) from exc

    return {"status": "ok"}
