import os

import httpx
import pytest
from sqlalchemy import create_engine, text

from app.config import Settings

pytestmark = pytest.mark.smoke


def _require_real_smoke() -> None:
    if os.getenv("RUN_REAL_SMOKE") != "1":
        pytest.skip(
            "Set RUN_REAL_SMOKE=1 after `docker compose up` to run real-service smoke tests"
        )


def test_real_fastapi_health_endpoint() -> None:
    _require_real_smoke()

    response = httpx.get("http://localhost:8000/health", timeout=10)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_real_qdrant_ready_endpoint() -> None:
    _require_real_smoke()

    settings = Settings()
    response = httpx.get(f"{settings.qdrant_url}/readyz", timeout=10)

    assert response.status_code == 200


def test_real_ollama_tags_endpoint() -> None:
    _require_real_smoke()

    settings = Settings()
    response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=10)
    model_names = {model["name"] for model in response.json().get("models", [])}

    assert response.status_code == 200
    assert settings.ollama_model in model_names
    assert settings.embedding_model in model_names


def test_real_postgres_pgvector_extension() -> None:
    _require_real_smoke()

    settings = Settings()
    engine = create_engine(settings.postgres_url)

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        extension = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()

    assert extension == "vector"
