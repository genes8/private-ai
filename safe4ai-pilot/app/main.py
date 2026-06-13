import asyncio
import contextlib
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from secrets import compare_digest
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from secure import Secure
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.account_routes import me_router
from app.api.account_routes import router as account_router
from app.api.audit_routes import router as audit_router
from app.api.chat_routes import router as chat_router
from app.api.document_routes import router as document_router
from app.api.observability_routes import router as observability_router
from app.api.review_routes import router as review_router
from app.api.settings_routes import router as settings_router
from app.api.user_routes import router as user_router
from app.auth.router import limiter as auth_limiter
from app.auth.router import router as auth_router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.security.pinned_http import create_pinned_async_transport
from app.services.runtime_config import build_runtime_components, load_runtime_config
from app.startup_migrations import run_startup_migrations
from scripts.audit_cleanup import schedule_cleanup

logger = structlog.get_logger(__name__)

secure_headers = Secure()


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from app.services.ingestion_service import recover_stuck_jobs

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    run_startup_migrations()

    with SessionLocal() as db:
        recover_stuck_jobs(db)
        runtime, retriever, reranker, graph = build_runtime_components(db)
    _app.state.retriever = retriever
    _app.state.reranker = reranker
    _app.state.graph = graph
    _app.state.ingestion_tasks = set()

    asyncio.create_task(_prewarm_provider(runtime))
    asyncio.create_task(_rebuild_bm25(retriever))
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

        # F-10: Always verify CSRF double-submit token for unsafe methods
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
    transfer_encoding = request.headers.get("transfer-encoding", "").lower()
    max_body_bytes = settings.max_upload_size_mb * 1024 * 1024

    # F-01: Reject ambiguous requests with both CL and TE (RFC 7230 §3.3.3)
    if content_length and transfer_encoding:
        return Response(
            status_code=400,
            content="Ambiguous body framing: both Content-Length and Transfer-Encoding present",
        )

    if content_length:
        try:
            length = int(content_length)
        except ValueError:
            return Response(status_code=400, content="Invalid content-length header")
        if length > max_body_bytes:
            return Response(status_code=413, content="Request body too large")
    elif transfer_encoding == "chunked":
        # F-02: All paths including /chat and /chat/stream are now checked
        spooled_body = None
        try:
            total_bytes = 0
            spooled_body = tempfile.SpooledTemporaryFile(max_size=max_body_bytes)
            async for chunk in request.stream():
                if chunk:
                    total_bytes += len(chunk)
                    spooled_body.write(chunk)
                if total_bytes > max_body_bytes:
                    spooled_body.close()
                    spooled_body = None
                    return Response(status_code=413, content="Request body too large")
            spooled_body.seek(0)
            buffered_body = spooled_body.read()
            spooled_body.close()
            spooled_body = None

            # F-05: Set _body so Starlette's body()/stream() return it
            # without consulting _stream_consumed or _receive.
            request._body = buffered_body  # type: ignore[attr-defined]
        except Exception:
            return Response(status_code=400, content="Failed to read request body")
        finally:
            if spooled_body is not None:
                spooled_body.close()
    return await call_next(request)


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(observability_router)
app.include_router(document_router)
app.include_router(user_router)
app.include_router(audit_router)
app.include_router(review_router)
app.include_router(settings_router)
app.include_router(account_router)
app.include_router(me_router)


async def _rebuild_bm25(retriever: Any) -> None:
    """Backfill workspace payloads (if needed), then rebuild the BM25 index.

    The workspace backfill rebuilds BM25 itself on success; if it is incomplete
    (e.g. Qdrant briefly unavailable) we still rebuild BM25 so the sparse path
    works for already-tagged points, and the scheduler retries the backfill.
    """
    from app.services.workspace_backfill import backfill_qdrant_workspace_payload

    try:
        done = await asyncio.to_thread(backfill_qdrant_workspace_payload, retriever)
        if done:
            return
    except Exception as exc:
        logger.warning("workspace_backfill_startup_failed", error=str(exc))
    try:
        count = await asyncio.to_thread(retriever.rebuild_from_qdrant)
        logger.info("bm25_index_rebuilt", chunk_count=count)
    except Exception as exc:
        logger.warning("bm25_rebuild_failed", error=str(exc))


async def _prewarm_provider(runtime: Any) -> None:
    """Warm the configured provider when it supports local Ollama preloading."""
    await asyncio.sleep(5)  # give Ollama container time to be fully ready
    if getattr(runtime, "provider_type", "ollama") != "ollama":
        logger.info(
            "provider_prewarm_skipped",
            provider_type=getattr(runtime, "provider_type", "unknown"),
        )
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
        # F-06: Do not expose connection details in unauthenticated endpoint
        logger.warning("health_postgres_failed", error=str(exc))
        checks["postgres"] = "error"

    # Qdrant
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.qdrant_url}/readyz")
            checks["qdrant"] = "ok" if r.status_code == 200 else "error"
    except Exception as exc:
        logger.warning("health_qdrant_failed", error=str(exc))
        checks["qdrant"] = "error"

    if runtime.provider_type == "openai_compatible":
        try:
            if not runtime.provider_api_key:
                checks["provider"] = "error"
            else:
                provider_resolved_ip = getattr(runtime, "provider_resolved_ip", None)
                transport = (
                    create_pinned_async_transport(
                        runtime.provider_base_url,
                        str(provider_resolved_ip),
                    )
                    if provider_resolved_ip and isinstance(provider_resolved_ip, str)
                    else None
                )
                async with httpx.AsyncClient(timeout=5, transport=transport) as client:
                    r = await client.get(
                        f"{runtime.provider_base_url}/models",
                        headers={"Authorization": f"Bearer {runtime.provider_api_key}"},
                    )
                    checks["provider"] = "ok" if r.status_code < 400 else "error"
        except Exception as exc:
            logger.warning("health_provider_failed", error=str(exc))
            checks["provider"] = "error"
    else:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{settings.ollama_url}/api/tags")
                checks["provider"] = "ok" if r.status_code == 200 else "error"
        except Exception as exc:
            logger.warning("health_provider_failed", error=str(exc))
            checks["provider"] = "error"

    # NOTE: the Qdrant workspace_id backfill status is intentionally NOT part of
    # this unauthenticated liveness probe — a pending backfill does not make the
    # service unhealthy, and /health must not do extra DB work or leak detail.
    # The operator-facing signal lives on GET /admin/workspace-backfill-status.

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
