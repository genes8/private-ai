import socket

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


def test_pg_container_has_pgvector_extension(pg_container: str) -> None:
    engine = create_engine(pg_container)

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        extension = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()

    assert extension == "vector"


def test_qdrant_container_ready_endpoint(qdrant_container: str) -> None:
    host, port = qdrant_container.removeprefix("http://").split(":")

    with socket.create_connection((host, int(port)), timeout=5):
        connected = True

    assert connected is True
