"""Unit tests for app.services.provider_settings.

These tests exercise policy functions directly — no TestClient, no mocked HTTP
app state required. Each function is a pure helper that returns a dict or raises
SettingsValidationError, so assertions are straightforward.
"""
from __future__ import annotations

import pytest

from app.services.provider_settings import (
    sanitize_ollama_role_models,
    validate_hybrid_embedding,
)
from app.services.settings_exceptions import SettingsValidationError

_GEN = "qwen3.5:9b"
_EMB = "nomic-embed-text"
_VIS = "qwen2.5vl:7b"
_DEFAULTS = dict(
    default_generation_model=_GEN,
    default_embedding_model=_EMB,
    default_vision_model=_VIS,
)
_ALL_AVAILABLE = {_GEN, _EMB, _VIS}


# ---------------------------------------------------------------------------
# sanitize_ollama_role_models — local mode
# ---------------------------------------------------------------------------


def test_sanitize_local_no_updates_when_all_models_available() -> None:
    """No updates when all DB models are already in the Ollama available set."""
    cfg = {"generation_model": _GEN, "embedding_model": _EMB, "vision_model": _VIS}
    updates = sanitize_ollama_role_models("local", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert updates == {}


def test_sanitize_local_resets_stale_chat_model() -> None:
    """Cloud generation_model is reset to the Ollama default."""
    cfg = {"generation_model": "deepseek-v4-flash", "embedding_model": _EMB, "vision_model": _VIS}
    updates = sanitize_ollama_role_models("local", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert updates["generation_model"] == _GEN
    assert "embedding_model" not in updates
    assert "vision_model" not in updates


def test_sanitize_local_resets_stale_embedding_model() -> None:
    """Cloud embedding_model is reset to the Ollama default."""
    cfg = {
        "generation_model": _GEN,
        "embedding_model": "text-embedding-3-small",
        "vision_model": _VIS,
    }
    updates = sanitize_ollama_role_models("local", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert updates["embedding_model"] == _EMB
    assert "generation_model" not in updates


def test_sanitize_local_resets_stale_vision_model() -> None:
    """Cloud vision_model is reset to the Ollama default."""
    cfg = {"generation_model": _GEN, "embedding_model": _EMB, "vision_model": "qwen-vl-plus"}
    updates = sanitize_ollama_role_models("local", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert updates["vision_model"] == _VIS
    assert "generation_model" not in updates
    assert "embedding_model" not in updates


def test_sanitize_local_resets_all_stale_cloud_models() -> None:
    """All three cloud slots are reset in one call."""
    cfg = {
        "generation_model": "deepseek-v4-flash",
        "embedding_model": "text-embedding-3-small",
        "vision_model": "qwen-vl-plus",
    }
    updates = sanitize_ollama_role_models("local", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert updates == {"generation_model": _GEN, "embedding_model": _EMB, "vision_model": _VIS}


def test_sanitize_local_raises_422_when_chat_default_unavailable() -> None:
    """Raises 422 when the current chat model is stale AND the default is also unavailable."""
    cfg = {"generation_model": "deepseek-v4-flash"}
    # Only embedding and vision defaults are available — not the chat default
    available = {_EMB, _VIS}
    with pytest.raises(SettingsValidationError) as exc_info:
        sanitize_ollama_role_models("local", cfg, available, **_DEFAULTS)
    assert _GEN in exc_info.value.detail


def test_sanitize_local_raises_422_when_embedding_default_unavailable() -> None:
    """Raises 422 when the current embedding model is stale AND the default is also unavailable."""
    cfg = {"generation_model": _GEN, "embedding_model": "text-embedding-3-small"}
    available = {_GEN, _VIS}
    with pytest.raises(SettingsValidationError) as exc_info:
        sanitize_ollama_role_models("local", cfg, available, **_DEFAULTS)
    assert _EMB in exc_info.value.detail


def test_sanitize_local_raises_422_when_vision_default_unavailable() -> None:
    """Raises 422 when vision model is stale AND the default is also unavailable."""
    cfg = {"generation_model": _GEN, "embedding_model": _EMB, "vision_model": "qwen-vl-plus"}
    available = {_GEN, _EMB}
    with pytest.raises(SettingsValidationError) as exc_info:
        sanitize_ollama_role_models("local", cfg, available, **_DEFAULTS)
    assert _VIS in exc_info.value.detail


# ---------------------------------------------------------------------------
# sanitize_ollama_role_models — hybrid mode
# ---------------------------------------------------------------------------


def test_sanitize_hybrid_does_not_touch_generation_model() -> None:
    """Hybrid mode must never reset generation_model — that is the cloud chat model."""
    cfg = {"generation_model": "deepseek-v4-flash", "embedding_model": _EMB, "vision_model": _VIS}
    updates = sanitize_ollama_role_models("hybrid", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert "generation_model" not in updates


def test_sanitize_hybrid_resets_stale_vision_model() -> None:
    """Cloud vision_model is reset in hybrid mode."""
    cfg = {
        "generation_model": "deepseek-v4-flash",
        "embedding_model": _EMB,
        "vision_model": "qwen-vl-plus",
    }
    updates = sanitize_ollama_role_models("hybrid", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert updates["vision_model"] == _VIS
    assert "generation_model" not in updates


def test_sanitize_hybrid_no_updates_when_vision_available() -> None:
    cfg = {"generation_model": "deepseek-v4-flash", "embedding_model": _EMB, "vision_model": _VIS}
    updates = sanitize_ollama_role_models("hybrid", cfg, _ALL_AVAILABLE, **_DEFAULTS)
    assert updates == {}


def test_sanitize_hybrid_raises_422_when_vision_default_unavailable() -> None:
    """Hybrid: raises 422 when stale vision model's default is also not in Ollama."""
    cfg = {"embedding_model": _EMB, "vision_model": "qwen-vl-plus"}
    available = {_EMB}  # vision default qwen2.5vl:7b NOT present
    with pytest.raises(SettingsValidationError) as exc_info:
        sanitize_ollama_role_models("hybrid", cfg, available, **_DEFAULTS)
    assert _VIS in exc_info.value.detail


# ---------------------------------------------------------------------------
# validate_hybrid_embedding — existing logic regression
# ---------------------------------------------------------------------------


def test_validate_hybrid_embedding_returns_none_when_requested_available() -> None:
    result = validate_hybrid_embedding(
        available_ollama={_EMB},
        current_embedding_model="text-embedding-3-small",
        requested_embedding_model=_EMB,
        default_embedding_model=_EMB,
    )
    assert result is None


def test_validate_hybrid_embedding_returns_default_when_requested_unavailable() -> None:
    result = validate_hybrid_embedding(
        available_ollama={_EMB},
        current_embedding_model="text-embedding-3-small",
        requested_embedding_model=None,
        default_embedding_model=_EMB,
    )
    assert result == _EMB


def test_validate_hybrid_embedding_raises_when_neither_available() -> None:
    with pytest.raises(SettingsValidationError) as exc_info:
        validate_hybrid_embedding(
            available_ollama={"some-other-model"},
            current_embedding_model="text-embedding-3-small",
            requested_embedding_model=None,
            default_embedding_model=_EMB,
        )
