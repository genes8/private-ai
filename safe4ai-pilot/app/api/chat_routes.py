"""Chat endpoints: blocking POST /chat (for eval scripts) and SSE POST /chat/stream."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import User
from app.models import Citation, Message, PrivateAIState
from app.services.chat_finalizer import finalize_chat_run
from app.services.conversation import ConversationManager
from app.services.cost_service import CostCeilingExceeded, check_cost_ceiling, usage_or_estimate
from app.services.runtime_config import load_runtime_config
logger = structlog.get_logger(__name__)


router = APIRouter(tags=["chat"])

# LangGraph node → SSE step name (handoff spec)
_STEP_MAP: dict[str, str] = {
    "intake": "embed",
    "rewrite": "embed",
    "retrieve": "retrieve",
    "grade": "rerank",
    "decompose": "rerank",
    "generate": "generate",
    "output_filter": "generate",
    "quality_gate": "generate",
    "respond": "generate",
    "fallback": "generate",
}


class ChatRequest(BaseModel):
    question: str = Field(..., max_length=2048)
    session_id: str | None = Field(None, max_length=36)
    collection: str = "default"

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        import re
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", v):
            raise ValueError("session_id must be a valid UUID")
        return v


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    session_id: str
    trace_id: str
    cache_hit: bool = False


def _resolve_session(
    body: ChatRequest, user_id: str, convo: ConversationManager
) -> tuple[str, PrivateAIState]:
    """Load existing session or create a new one. Returns (session_id, state)."""
    if body.session_id:
        try:
            state = convo.load_session(body.session_id)
            if state.user_id != user_id:
                raise HTTPException(status_code=404, detail="Session not found")
            return body.session_id, state
        except (KeyError, ValueError):
            # KeyError: session not found — create a new one
            # ValueError: session state corrupted — create a new one
            pass
    session_id = convo.new_session(user_id)
    return session_id, convo.load_session(session_id)


def _build_run_state(
    state: PrivateAIState, question: str, trace_id: str
) -> PrivateAIState:
    user_msg = Message(role="user", content=question, created_at=datetime.now(UTC))
    return state.model_copy(
        update={
            "messages": list(state.messages) + [user_msg],
            "current_step": "intake",
            "status": "active",
            "trace_id": trace_id,
            "rewritten_query": "",
            "retrieved_chunks": [],
            "graded_chunks": [],
            "draft_answer": "",
            "citations": [],
            "errors": [],
            "retrieval_attempts": 0,
            "generation_context": [],
        }
    )


def _merge_stream_state(current: PrivateAIState, update: PrivateAIState | dict[str, Any]) -> PrivateAIState:
    if isinstance(update, PrivateAIState):
        return update
    merged = current.model_dump()
    merged.update(update)
    return PrivateAIState(**merged)


# ---------------------------------------------------------------------------
# POST /chat — blocking, no frontend consumer.
# Intentionally kept for offline_eval.py, integration tests, and direct
# API clients that need a single-shot synchronous response.
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty")

    try:
        check_cost_ceiling(db, projected_question=body.question)
    except CostCeilingExceeded as exc:
        raise HTTPException(status_code=429, detail=exc.detail) from exc

    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="AI pipeline not ready")

    convo = ConversationManager(db)
    session_id, state = _resolve_session(body, str(current_user.id), convo)
    trace_id = str(uuid.uuid4())
    run_state = _build_run_state(state, body.question, trace_id)

    started_at = time.monotonic()
    try:
        raw_final = await graph.ainvoke(run_state)
        # LangGraph ainvoke returns a dict; convert to model if needed
        final = PrivateAIState(**raw_final) if isinstance(raw_final, dict) else raw_final
    except Exception as exc:
        logger.error("graph_invocation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Pipeline error") from exc

    latency_ms = int((time.monotonic() - started_at) * 1000)
    try:
        runtime_cfg = load_runtime_config(db)
        _chat_model_name = runtime_cfg.chat_model
    except Exception:
        _chat_model_name = settings.ollama_model
    usage = usage_or_estimate(body.question, final.draft_answer or "", final.provider_usage)
    try:
        finalize_chat_run(
            db=db,
            final=final,
            user_id=str(current_user.id),
            query=body.question,
            latency_ms=latency_ms,
            k_retrieved=len(final.retrieved_chunks),
            usage=usage,
            cost_per_1k_tokens=settings.cost_per_1k_tokens,
            model_name=_chat_model_name,
        )
    except Exception as exc:
        logger.warning("finalize_chat_run_failed", error=str(exc))

    return ChatResponse(
        answer=final.draft_answer,
        citations=final.citations,
        session_id=session_id,
        trace_id=final.trace_id,
    )


# ---------------------------------------------------------------------------
# POST /chat/stream — SSE streaming (used by frontend)
# ---------------------------------------------------------------------------


@router.post("/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty")

    try:
        check_cost_ceiling(db, projected_question=body.question)
    except CostCeilingExceeded as exc:
        raise HTTPException(status_code=429, detail=exc.detail) from exc

    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="AI pipeline not ready")

    convo = ConversationManager(db)
    session_id, state = _resolve_session(body, str(current_user.id), convo)
    trace_id = str(uuid.uuid4())
    run_state = _build_run_state(state, body.question, trace_id)

    async def event_stream() -> AsyncIterator[str]:
        def _sse(event: str, data: dict[str, Any]) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        started_at = time.monotonic()
        final: PrivateAIState | None = None
        stream_state = run_state
        active_step: str | None = None

        try:
            # Stream node-by-node via LangGraph astream
            async for chunk in graph.astream(run_state):
                if await request.is_disconnected():
                    logger.info("sse_client_disconnected", trace_id=trace_id)
                    return
                for node_name in chunk:
                    step_name = _STEP_MAP.get(node_name)
                    # Close previous active step
                    if active_step and step_name and active_step != step_name:
                        yield _sse("step", {"name": active_step, "state": "done", "t": 0})

                    if step_name:
                        yield _sse("step", {"name": step_name, "state": "active", "t": 0})
                        active_step = step_name

                    # Capture the last node state as final
                    node_state = chunk[node_name]
                    if isinstance(node_state, PrivateAIState | dict):
                        stream_state = _merge_stream_state(stream_state, node_state)
                        final = stream_state

            # Close last step
            if active_step:
                yield _sse("step", {"name": active_step, "state": "done", "t": 0})

        except Exception as exc:
            logger.error("graph_stream_failed", error=str(exc))
            # F-07: Do not leak internal error details to the client
            yield _sse("done", {"error": "Pipeline error", "traceId": trace_id, "sessionId": session_id})
            return

        if final is None:
            yield _sse("done", {"error": "no output", "traceId": trace_id, "sessionId": session_id})
            return

        # Stream answer tokens (word-by-word, 20 ms gap)
        words = final.draft_answer.split(" ") if final.draft_answer else []
        for i, word in enumerate(words):
            delta = word if i == len(words) - 1 else word + " "
            yield _sse("token", {"delta": delta})
            await asyncio.sleep(0.02)

        # Emit citations
        for idx, c in enumerate(final.citations, start=1):
            yield _sse("cite", {
                "id": str(idx),
                "file": c.filename,
                "page": c.page_number,
                "score": c.score,
                "excerpt": c.excerpt,
            })

        latency_ms = int((time.monotonic() - started_at) * 1000)

        usage = usage_or_estimate(
            body.question,
            final.draft_answer or "",
            final.provider_usage,
        )

        runtime = None
        try:
            runtime = load_runtime_config(db)
            sse_done_mode = runtime.sse_done_mode
        except Exception:
            sse_done_mode = "strict"

        _model_name = runtime.chat_model if runtime is not None else settings.ollama_model

        async def _finalize_run(target_db: Session) -> None:
            try:
                finalize_chat_run(
                    db=target_db,
                    final=final,
                    user_id=str(current_user.id),
                    query=body.question,
                    latency_ms=latency_ms,
                    k_retrieved=len(final.retrieved_chunks),
                    usage=usage,
                    cost_per_1k_tokens=settings.cost_per_1k_tokens,
                    model_name=_model_name,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "chat_stream_postprocessing_failed",
                    error=str(exc),
                    trace_id=final.trace_id,
                )

        if sse_done_mode == "async":
            from app.db import SessionLocal

            async def _finalize_in_new_session() -> None:
                with SessionLocal() as async_db:
                    await _finalize_run(async_db)

            asyncio.create_task(_finalize_in_new_session())
        else:
            await _finalize_run(db)

        yield _sse("done", {
            "traceId": final.trace_id,
            "latencyMs": latency_ms,
            "cache": False,
            "model": runtime.provider_type if runtime is not None else "local",
            "kRetrieved": len(final.retrieved_chunks),
            "sessionId": session_id,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
