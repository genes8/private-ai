"""Verify all services are reachable. Exits non-zero if any fail."""

import sys

import httpx
from sqlalchemy import text

from app.config import settings
from app.db import engine


def check_postgres() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("postgres: ok")
        return True
    except Exception as exc:
        print(f"postgres: FAIL — {exc}")
        return False


def check_qdrant() -> bool:
    try:
        r = httpx.get(f"{settings.qdrant_url}/readyz", timeout=5)
        if r.status_code == 200:
            print("qdrant: ok")
            return True
        print(f"qdrant: FAIL — status {r.status_code}")
        return False
    except Exception as exc:
        print(f"qdrant: FAIL — {exc}")
        return False


def check_ollama() -> bool:
    try:
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=5)
        if r.status_code == 200:
            print("ollama: ok")
            return True
        print(f"ollama: FAIL — status {r.status_code}")
        return False
    except Exception as exc:
        print(f"ollama: FAIL — {exc}")
        return False


def main() -> None:
    results = [check_postgres(), check_qdrant(), check_ollama()]
    if not all(results):
        sys.exit(1)
    print("All services healthy.")


if __name__ == "__main__":
    main()
