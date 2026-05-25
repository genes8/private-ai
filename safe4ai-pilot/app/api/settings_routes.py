from __future__ import annotations

from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.middleware import require_role
from app.auth.router import limiter
from app.db import get_db
from app.db.models import User
from app.services.app_config_store import load_app_config, upsert_app_config
from app.security.url_validator import validate_provider_url
from app.services.provider_settings import resolve_provider_config
from app.services.runtime_config import build_runtime_components
from app.services.settings_service import (
    PatchSettingsRequest,
    collect_field_updates,
    invalidate_live_cache,
    normalize_patch_request,
    probe_provider_prerequisites,
    serialize_settings,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["settings"])


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
    return serialize_settings(db)


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
    invalidate_live_cache()
    logger.info("settings_updated", keys=list(updates.keys()))
    result = serialize_settings(db)
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
