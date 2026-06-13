"""Thin authenticated HTTP client for real-service smoke tests.

Talks to a running stack at ``http://localhost:8000``. Handles the double-submit
CSRF flow (GET /auth/csrf -> POST /auth/login with the X-CSRF-Token header) and
keeps the session cookie + CSRF token for subsequent admin calls.

Admin credentials come from the environment so the test never hardcodes a
password: ``SMOKE_ADMIN_EMAIL`` (default ``admin@safe4ai.local``) and
``SMOKE_ADMIN_PASSWORD`` (falls back to ``SEED_ADMIN_PASSWORD``).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, cast

import httpx

_BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:8000")


class SmokeAuthError(RuntimeError):
    """Raised when smoke admin credentials are missing or rejected."""


class SmokeClient:
    """Authenticated client bound to a live Safe4AI deployment."""

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=30)
        self._csrf: str | None = None

    def __enter__(self) -> SmokeClient:
        self.login()
        return self

    def __exit__(self, *exc: object) -> None:
        self._http.close()

    def login(self) -> None:
        email = os.getenv("SMOKE_ADMIN_EMAIL", "admin@safe4ai.local")
        password = os.getenv("SMOKE_ADMIN_PASSWORD") or os.getenv("SEED_ADMIN_PASSWORD")
        if not password:
            raise SmokeAuthError(
                "Set SMOKE_ADMIN_PASSWORD (or SEED_ADMIN_PASSWORD) for smoke auth"
            )

        csrf = self._http.get("/auth/csrf")
        csrf.raise_for_status()
        token = str(csrf.json()["csrf_token"])
        self._csrf = token

        resp = self._http.post(
            "/auth/login",
            json={"email": email, "password": password},
            headers={"X-CSRF-Token": token},
        )
        if resp.status_code != 200:
            raise SmokeAuthError(f"login failed ({resp.status_code}): {resp.text}")
        # The login response rotates the CSRF cookie; pick up the fresh value.
        self._csrf = self._http.cookies.get("csrf_token", token)

    def _headers(self) -> dict[str, str]:
        return {"X-CSRF-Token": self._csrf} if self._csrf else {}

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._http.get(path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        return self._http.post(path, headers=headers, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        return self._http.delete(path, headers=headers, **kwargs)

    # --- document helpers ----------------------------------------------------

    def upload_document(self, path: Path) -> str:
        """Upload a new document, returning its doc_id."""
        with path.open("rb") as fh:
            resp = self.post(
                "/admin/documents/upload",
                files={"file": (path.name, fh, "application/pdf")},
            )
        resp.raise_for_status()
        return str(resp.json()["doc_id"])

    def upload_new_version(self, doc_id: str, path: Path) -> dict[str, Any]:
        with path.open("rb") as fh:
            resp = self.post(
                f"/admin/documents/{doc_id}/upload-new-version",
                files={"file": (path.name, fh, "application/pdf")},
            )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def status(self, doc_id: str) -> dict[str, Any]:
        resp = self.get(f"/admin/documents/{doc_id}/status")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def inspect(self, doc_id: str) -> dict[str, Any]:
        resp = self.get(f"/admin/documents/{doc_id}/inspect")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def wait_for_indexed(self, doc_id: str, timeout: float = 180.0) -> dict[str, Any]:
        """Poll status until the document reaches a terminal ingestion state."""
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.status(doc_id)
            if last.get("ingestion_status") in {"indexed", "failed", "skipped"}:
                return last
            time.sleep(2)
        raise TimeoutError(f"document {doc_id} did not finish ingesting: {last}")
