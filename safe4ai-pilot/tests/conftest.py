from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient


def _docker_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Mock Ollama transport — returns canned responses without hitting real Ollama
# ---------------------------------------------------------------------------

FAKE_EMBEDDING = [0.1] * 768
FAKE_GENERATE_RESPONSE = {
    "model": "qwen3.5:9b",
    "response": "This is a test response.",
    "done": True,
}
FAKE_EMBED_RESPONSE = {"embedding": FAKE_EMBEDDING}
FAKE_TAGS_RESPONSE = {"models": [{"name": "qwen3.5:9b"}, {"name": "nomic-embed-text"}]}


class MockOllamaTransport(httpx.BaseTransport):
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/generate":
            return httpx.Response(200, json=FAKE_GENERATE_RESPONSE)
        if path == "/api/embeddings":
            return httpx.Response(200, json=FAKE_EMBED_RESPONSE)
        if path == "/api/tags":
            return httpx.Response(200, json=FAKE_TAGS_RESPONSE)
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture(scope="session")
def mock_ollama() -> httpx.Client:
    return httpx.Client(transport=MockOllamaTransport())


# ---------------------------------------------------------------------------
# FastAPI test client (unit tests — no real DB, uses mock Ollama)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def pg_container() -> Generator[str, None, None]:
    if not _docker_available():
        pytest.skip("Docker is required for pg_container integration tests")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:0.8.0-pg16") as postgres:
        yield postgres.get_connection_url(driver="psycopg2")


@pytest.fixture(scope="session")
def qdrant_container() -> Generator[str, None, None]:
    if not _docker_available():
        pytest.skip("Docker is required for qdrant_container integration tests")

    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    with DockerContainer("qdrant/qdrant:v1.13.3").with_exposed_ports(6333) as qdrant:
        wait_for_logs(qdrant, "Qdrant HTTP listening")
        host = qdrant.get_container_host_ip()
        port = qdrant.get_exposed_port(6333)
        yield f"http://{host}:{port}"
