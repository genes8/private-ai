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
_ORIGIN = os.getenv("SMOKE_ORIGIN", "http://localhost:3000")


class SmokeAuthError(RuntimeError):
    """Raised when smoke admin credentials are missing or rejected."""


class SmokeClient:
    """Authenticated client bound to a live Safe4AI deployment."""

    def __init__(self, base_url: str = _BASE_URL) -> None:
        # Ingestion shares the request event loop; while OCR/embedding is in
        # flight, status polling can block behind it. Allow up to 120s per call
        # so polling survives a cold model load on the first OCR.
        self._http = httpx.Client(base_url=base_url, timeout=120)
        self._csrf: str | None = None
        self._workspace_id: str | None = None

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
            headers={"Origin": _ORIGIN, "X-CSRF-Token": token},
        )
        if resp.status_code != 200:
            raise SmokeAuthError(f"login failed ({resp.status_code}): {resp.text}")
        # The login response rotates the CSRF cookie; pick up the fresh value.
        self._csrf = self._http.cookies.get("csrf_token", token)
        self._workspace_id = self._resolve_workspace_id()

    def _resolve_workspace_id(self) -> str:
        env_id = os.getenv("SMOKE_WORKSPACE_ID")
        if env_id:
            return env_id
        listed = self._http.get("/workspaces", headers={"X-CSRF-Token": self._csrf or ""})
        listed.raise_for_status()
        rows = listed.json()
        if rows:
            return str(rows[0]["id"])
        created = self._http.post(
            "/admin/workspaces",
            json={"name": "Smoke Tests", "slug": "smoke-tests"},
            headers={"X-CSRF-Token": self._csrf or ""},
        )
        created.raise_for_status()
        return str(created.json()["id"])

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._csrf:
            headers["X-CSRF-Token"] = self._csrf
        if self._workspace_id:
            headers["X-Workspace-Id"] = self._workspace_id
        return headers

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
