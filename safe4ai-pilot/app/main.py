import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from secure import Secure
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.observability_routes import router as observability_router
from app.auth.router import limiter as auth_limiter
from app.auth.router import router as auth_router
from app.config import settings
from app.db import engine
from scripts.audit_cleanup import schedule_cleanup

logger = structlog.get_logger(__name__)

secure_headers = Secure()


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    asyncio.create_task(_prewarm_ollama())
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
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def set_secure_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.update(secure_headers.headers())
    return response


@app.middleware("http")
async def limit_body_size(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > (settings.max_upload_size_mb + 10) * 1024 * 1024:
        return Response(status_code=413, content="Request body too large")
    return await call_next(request)


app.include_router(auth_router)
app.include_router(observability_router)


async def _prewarm_ollama() -> None:
    """Hit Ollama with an empty prompt so the model is loaded before first real query."""
    await asyncio.sleep(5)  # give Ollama container time to be fully ready
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(
                f"{settings.ollama_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": "", "stream": False},
            )
        logger.info("ollama_prewarm_complete", model=settings.ollama_model)
    except Exception as exc:
        logger.warning("ollama_prewarm_failed", error=str(exc))


@app.get("/health")
async def health() -> dict[str, object]:
    checks: dict[str, str] = {}

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

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.ollama_url}/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else f"status {r.status_code}"
    except Exception as exc:
        checks["ollama"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
