import asyncio
import contextlib
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from secure import Secure
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.admin_routes import router as admin_router
from app.api.chat_routes import router as chat_router
from app.api.observability_routes import router as observability_router
from app.auth.router import limiter as auth_limiter
from app.auth.router import router as auth_router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.services.runtime_config import build_runtime_components, load_runtime_config
from scripts.audit_cleanup import schedule_cleanup

logger = structlog.get_logger(__name__)

secure_headers = Secure()
_QDRANT_COLLECTION = "documents"
_QDRANT_VECTOR_SIZE = 768
_DELETED_USER_ID = "00000000-0000-0000-0000-000000000001"
_DELETED_USER_EMAIL = "deleted@redacted.local"


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from app.services.ingestion_service import recover_stuck_jobs

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    _ensure_documents_columns()
    _ensure_user_columns()
    _ensure_document_foreign_keys()
    _ensure_deleted_user()
    _ensure_qdrant_collection()

    with SessionLocal() as db:
        recover_stuck_jobs(db)
        runtime, retriever, reranker, graph = build_runtime_components(db)
    _app.state.retriever = retriever
    _app.state.reranker = reranker
    _app.state.graph = graph
    _app.state.ingestion_tasks = set()

    asyncio.create_task(_prewarm_provider(runtime))
    schedule_cleanup(_app)
    yield


app = FastAPI(title="Safe4AI Pilot", lifespan=lifespan)
# Use the same Limiter instance that decorates auth routes so the
# SlowAPI middleware can enforce rate limits correctly.
app.state.limiter = auth_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def set_secure_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.update(secure_headers.headers())
    return response


@app.middleware("http")
async def protect_csrf(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    unsafe_methods = {"POST", "PUT", "PATCH", "DELETE"}
    if request.method in unsafe_methods:
        origin = request.headers.get("origin")
        requires_origin_check = request.url.path == "/auth/login"
        if requires_origin_check and not origin:
            response = JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
            response.headers.update(secure_headers.headers())
            return response
        if origin and origin not in settings.allowed_origins_list:
            response = JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
            response.headers.update(secure_headers.headers())
            return response

        # Verify CSRF double-submit token for all authenticated requests and always for login
        needs_csrf = (
            request.cookies.get("access_token")
            or request.cookies.get("csrf_token")
            or request.url.path == "/auth/login"
        )
        if needs_csrf:
            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("X-CSRF-Token")
            if not csrf_cookie or not csrf_header or not compare_digest(csrf_header, csrf_cookie):
                response = JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
                response.headers.update(secure_headers.headers())
                return response
    return await call_next(request)


@app.middleware("http")
async def limit_body_size(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    content_length = request.headers.get("content-length")
    max_body_bytes = settings.max_upload_size_mb * 1024 * 1024
    if content_length:
        try:
            length = int(content_length)
        except ValueError:
            return Response(status_code=400, content="Invalid content-length header")
        if length > max_body_bytes:
            return Response(status_code=413, content="Request body too large")
    elif request.headers.get("transfer-encoding", "").lower() == "chunked":
        # Skip chunked body replay for chat streaming — the body is always tiny JSON
        # and the replay mechanism uses private ASGI internals that may break across versions.
        if request.url.path not in {"/chat/stream", "/chat"}:
            try:
                total_bytes = 0
                spooled_body = tempfile.SpooledTemporaryFile(max_size=max_body_bytes)
                replay_done = False
                async for chunk in request.stream():
                    if chunk:
                        total_bytes += len(chunk)
                        spooled_body.write(chunk)
                    if total_bytes > max_body_bytes:
                        spooled_body.close()
                        return Response(status_code=413, content="Request body too large")
                spooled_body.seek(0)

                async def replay_receive() -> dict[str, object]:
                    nonlocal replay_done
                    chunk = spooled_body.read(64 * 1024)
                    if chunk:
                        return {
                            "type": "http.request",
                            "body": chunk,
                            "more_body": spooled_body.tell() < total_bytes,
                        }
                    if replay_done:
                        return {"type": "http.request", "body": b"", "more_body": False}
                    replay_done = True
                    spooled_body.close()
                    return {"type": "http.request", "body": b"", "more_body": False}

                request._stream_consumed = False
                request._receive = replay_receive
            except Exception:
                return Response(status_code=400, content="Failed to read request body")
    return await call_next(request)


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(observability_router)
app.include_router(admin_router)


async def _prewarm_provider(runtime: Any) -> None:
    """Warm the configured provider when it supports local Ollama preloading."""
    await asyncio.sleep(5)  # give Ollama container time to be fully ready
    if getattr(runtime, "provider_type", "ollama") != "ollama":
        logger.info("provider_prewarm_skipped", provider_type=getattr(runtime, "provider_type", "unknown"))
        return
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(
                f"{settings.ollama_url}/api/generate",
                json={"model": runtime.chat_model, "prompt": "", "stream": False},
            )
        logger.info("ollama_prewarm_complete", model=runtime.chat_model)
    except Exception as exc:
        logger.warning("ollama_prewarm_failed", error=str(exc))


def _ensure_qdrant_collection() -> None:
    """Create the default document collection on first boot if it is missing.

    If the collection already exists, validates its vector size against the
    configured embedding model.  Raises RuntimeError on dimension mismatch so
    that startup fails loudly rather than silently producing wrong embeddings.
    """
    from app.services.runtime_config import expected_vector_size, load_runtime_config

    with SessionLocal() as db:
        runtime = load_runtime_config(db)
    embedding_model = runtime.embedding_model

    try:
        client = QdrantClient(url=settings.qdrant_url)
        if client.collection_exists(_QDRANT_COLLECTION):
            expected = expected_vector_size(embedding_model)
            if expected is not None:
                info = client.get_collection(_QDRANT_COLLECTION)
                vectors_cfg = info.config.params.vectors
                actual_size: int = (
                    next(iter(vectors_cfg.values())).size  # type: ignore[union-attr]
                    if isinstance(vectors_cfg, dict)
                    else vectors_cfg.size  # type: ignore[union-attr]
                )
                if actual_size != expected:
                    raise RuntimeError(
                        f"Qdrant collection '{_QDRANT_COLLECTION}' has vector size {actual_size} "
                        f"but embedding model '{embedding_model}' requires {expected}. "
                        "Drop and recreate the collection to switch embedding models."
                    )
            return
        client.create_collection(
            collection_name=_QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(
                size=_QDRANT_VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.info(
            "qdrant_collection_created",
            collection=_QDRANT_COLLECTION,
            vector_size=_QDRANT_VECTOR_SIZE,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning("qdrant_collection_ensure_failed", error=str(exc))


def _ensure_documents_columns() -> None:
    """Backfill document columns that older volumes may not have."""
    statements = [
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size_bytes INTEGER",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS active_version INTEGER DEFAULT 1",
    ]
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("document_columns_ensure_failed", error=str(exc))


def _ensure_user_columns() -> None:
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_valid_after TIMESTAMPTZ",
    ]
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("user_columns_ensure_failed", error=str(exc))


def _ensure_document_foreign_keys() -> None:
    statements = [
        f"ALTER TABLE documents ALTER COLUMN uploaded_by SET DEFAULT '{_DELETED_USER_ID}'",
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_uploaded_by_fkey",
        (
            "ALTER TABLE documents ADD CONSTRAINT documents_uploaded_by_fkey "
            "FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET DEFAULT"
        ),
    ]
    try:
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    except Exception as exc:
        logger.warning("document_foreign_keys_ensure_failed", error=str(exc))


def _ensure_deleted_user() -> None:
    from app.auth.middleware import hash_password

    statement = text(
        """
        INSERT INTO users (id, email, password_hash, role, is_active)
        SELECT :user_id, :email, :password_hash, :role, false
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = :user_id OR email = :email)
        """
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                statement,
                {
                    "user_id": _DELETED_USER_ID,
                    "email": _DELETED_USER_EMAIL,
                    "password_hash": hash_password(token_urlsafe(24)),
                    "role": "pilot_user",
                },
            )
    except Exception as exc:
        logger.warning("deleted_user_ensure_failed", error=str(exc))


@app.get("/health")
async def health() -> dict[str, object]:
    checks: dict[str, str] = {}
    with SessionLocal() as db:
        runtime = load_runtime_config(db)

    # PostgreSQL
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    # Qdrant
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.qdrant_url}/readyz")
            checks["qdrant"] = "ok" if r.status_code == 200 else f"status {r.status_code}"
    except Exception as exc:
        checks["qdrant"] = f"error: {exc}"

    if runtime.provider_type == "openai_compatible":
        try:
            if not runtime.provider_api_key:
                checks["provider"] = "error: missing api key"
            else:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(
                        f"{runtime.provider_base_url}/models",
                        headers={"Authorization": f"Bearer {runtime.provider_api_key}"},
                    )
                    checks["provider"] = "ok" if r.status_code < 400 else f"status {r.status_code}"
        except Exception as exc:
            checks["provider"] = f"error: {exc}"
    else:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{settings.ollama_url}/api/tags")
                checks["provider"] = "ok" if r.status_code == 200 else f"status {r.status_code}"
        except Exception as exc:
            checks["provider"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
