"""Provider-mode resolution: expands shorthand modes and validates pre-conditions.

The route handler (patch_settings) calls these functions to keep provider-mode
policy out of the HTTP layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from app.config import settings
from app.security.pinned_http import create_pinned_transport
from app.security.url_validator import validate_provider_url
from app.services.settings_exceptions import SettingsValidationError


@dataclass(frozen=True)
class ProviderResolution:
    """Canonical, validated provider state derived from raw DB config."""

    provider_type: str   # "ollama" | "openai_compatible"
    embedding_source: str  # "ollama" | "provider"
    provider_mode: str   # "local" | "hybrid" | "cloud"


@dataclass
class ProviderPatch:
    """Two-part delta from a mode shorthand: DB pre-updates and body field overrides."""

    pre_updates: dict[str, Any] = field(default_factory=dict)
    body_overrides: dict[str, Any] = field(default_factory=dict)


def resolve_provider_config(raw_config: dict[str, Any]) -> ProviderResolution:
    """Return canonical provider state from raw DB config.

    Enforces the invariant: ollama provider always uses ollama embeddings.
    """
    provider_type = str(raw_config.get("provider_type", "ollama"))
    if provider_type not in {"ollama", "openai_compatible"}:
        provider_type = "ollama"

    _default_embedding_source = "provider" if provider_type == "openai_compatible" else "ollama"
    embedding_source = str(raw_config.get("embedding_source", _default_embedding_source))
    if embedding_source not in {"ollama", "provider"}:
        embedding_source = _default_embedding_source
    if provider_type == "ollama":
        embedding_source = "ollama"

    if provider_type == "ollama":
        provider_mode = "local"
    elif embedding_source == "ollama":
        provider_mode = "hybrid"
    else:
        provider_mode = "cloud"

    return ProviderResolution(
        provider_type=provider_type,
        embedding_source=embedding_source,
        provider_mode=provider_mode,
    )


def expand_provider_mode(
    provider_mode: str,
    provider_base_url: str | None,
) -> ProviderPatch:
    """Expand a mode shorthand into constituent raw config fields.

    local   → Ollama for everything, base URL reset to local address
    hybrid  → cloud LLM + local Ollama for embeddings/vision
    cloud   → cloud provider for everything (requires /embeddings support)
    """
    if provider_mode == "local":
        return ProviderPatch(
            pre_updates={"provider_base_url": settings.ollama_url.rstrip("/")},
            body_overrides={
                "providerType": "ollama",
                "embeddingSource": "ollama",
                "providerBaseUrl": None,
            },
        )
    if provider_mode == "hybrid":
        return ProviderPatch(
            body_overrides={
                "providerType": "openai_compatible",
                "embeddingSource": "ollama",
                "providerBaseUrl": provider_base_url or "https://api.deepseek.com/v1",
            },
        )
    if provider_mode == "cloud":
        return ProviderPatch(
            body_overrides={"providerType": "openai_compatible", "embeddingSource": "provider"},
        )
    raise SettingsValidationError("providerMode must be local, hybrid, or cloud")


def validate_hybrid_embedding(
    *,
    available_ollama: set[str],
    current_embedding_model: str,
    requested_embedding_model: str | None,
    default_embedding_model: str,
) -> str | None:
    """Verify the embedding model is available in Ollama for hybrid mode.

    Returns a fallback model name if the requested model is unavailable but the
    settings default is.  Returns None when the requested model is already available.
    Raises SettingsValidationError when neither the requested nor default model is present.
    """
    effective = requested_embedding_model or current_embedding_model
    if effective in available_ollama:
        return None
    if default_embedding_model in available_ollama:
        return default_embedding_model
    raise SettingsValidationError(
        f"Embedding model '{default_embedding_model}' is not available in Ollama. "
        f"Pull it with: ollama pull {default_embedding_model}"
    )


def _sanitize_model_slot(
    db_key: str,
    current_config: dict[str, Any],
    default: str,
    available: set[str],
    updates: dict[str, Any],
) -> None:
    """Reset a stale model slot or raise 422 if the default is also unavailable."""
    current = str(current_config.get(db_key, default))
    if current in available:
        return
    if default in available:
        updates[db_key] = default
        return
    raise SettingsValidationError(
        f"'{default}' is not available in Ollama. Pull it with: ollama pull {default}"
    )


def sanitize_ollama_role_models(
    mode: Literal["local", "hybrid"],
    current_config: dict[str, Any],
    available_ollama: set[str],
    *,
    default_generation_model: str,
    default_embedding_model: str,
    default_vision_model: str,
) -> dict[str, Any]:
    """Return DB updates that replace stale non-Ollama model IDs in Ollama-backed slots.

    local:  generation_model, embedding_model, vision_model
    hybrid: vision_model only (embedding is handled separately by validate_hybrid_embedding)

    Raises SettingsValidationError when a role's default fallback is also absent from Ollama,
    so the caller never commits a config the runtime cannot use.
    """
    updates: dict[str, Any] = {}

    if mode == "local":
        _sanitize_model_slot(
            "generation_model", current_config, default_generation_model, available_ollama, updates
        )
        _sanitize_model_slot(
            "embedding_model", current_config, default_embedding_model, available_ollama, updates
        )
    elif mode != "hybrid":
        raise ValueError(f"sanitize_ollama_role_models: unknown mode {mode!r}")

    _sanitize_model_slot(
        "vision_model", current_config, default_vision_model, available_ollama, updates
    )

    return updates


def probe_cloud_embeddings(
    *,
    base_url: str,
    api_key: str,
    embedding_model: str,
) -> None:
    """Probe the provider's /embeddings endpoint for cloud mode.

    Raises SettingsValidationError on non-200 responses (provider does not support
    embeddings, e.g. DeepSeek) and on network failures (wrong URL, DNS, TLS).
    build_runtime_components() constructs clients without calling /embeddings,
    so a failing probe must be surfaced here — there is no later catch.
    """
    if not (base_url and api_key and embedding_model):
        return
    try:
        clean_url, resolved_ip = validate_provider_url(base_url)
        with httpx.Client(
            timeout=5.0,
            transport=create_pinned_transport(clean_url, resolved_ip),
        ) as client:
            resp = client.post(
                f"{clean_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": embedding_model, "input": "test"},
            )
        if resp.status_code != 200:
            raise SettingsValidationError(
                "This provider does not appear to support embeddings "
                f"(expected HTTP 200, got {resp.status_code}). "
                "Use Hybrid mode instead: cloud chat + local Ollama embeddings."
            )
    except SettingsValidationError:
        raise
    except httpx.TimeoutException as exc:
        raise SettingsValidationError(
            f"Embedding endpoint timed out ({base_url}). Check the URL and try again."
        ) from exc
    except Exception as exc:
        if getattr(exc, "status_code", None) == 422:
            raise SettingsValidationError(str(getattr(exc, "detail", exc))) from exc
        raise SettingsValidationError(
            f"Could not reach embedding endpoint ({base_url}): {exc}"
        ) from exc
