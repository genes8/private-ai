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
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user
from app.auth.router import limiter
from app.config import settings
from app.db import get_db
from app.db.models import AuditLog, User
from app.models import Citation, Message, PrivateAIState
from app.services.conversation import ConversationManager
from observability.cost_tracker import CostTracker

logger = structlog.get_logger(__name__)


def _write_audit_log(
    db: Session,
    *,
    user_id: str,
    session_id: str,
    query: str,
    trace_id: str,
    latency_ms: int,
    k_retrieved: int,
    status: str = "completed",
) -> None:
    """Append an audit-log row. Swallows errors so logging never breaks the response."""
    try:
        entry = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            action_type="chat_query",
            query_text=query[:500],
            response_metadata={
                "trace_id": trace_id,
                "k_retrieved": k_retrieved,
                "status": status,
            },
            latency_ms=latency_ms,
            model_used=settings.ollama_model,
            trace_id=trace_id,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.warning("audit_log_failed", error=str(exc))


def _record_cost(
    db: Session,
    session_id: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Record agent-run cost. Swallows errors so costing never breaks the response."""
    try:
        tracker = CostTracker(settings.cost_per_1k_tokens)
        tracker.record_run(
            db,
            session_id=session_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=settings.ollama_model,
            status="completed",
        )
    except Exception as exc:
        logger.warning("cost_tracking_failed", error=str(exc))


def _check_cost_ceiling(db: Session) -> None:
    """Raise 429 if the daily or monthly cost ceiling has been reached."""
    try:
        from app.services.app_config_store import load_app_config
        db_overrides = load_app_config(db)
        daily_ceiling = float(db_overrides.get("daily_ceiling_usd", 50))
        monthly_ceiling = float(db_overrides.get("monthly_ceiling_usd", 500))
        tracker = CostTracker(settings.cost_per_1k_tokens)
        today_cost = tracker.get_stats(db, days=1)["total_cost_usd"]
        if today_cost >= daily_ceiling:
            raise HTTPException(
                status_code=429,
                detail=f"Daily cost ceiling reached (${today_cost:.2f} / ${daily_ceiling:.2f})",
            )
        month_cost = tracker.get_stats(db, days=30)["total_cost_usd"]
        if month_cost >= monthly_ceiling:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly cost ceiling reached (${month_cost:.2f} / ${monthly_ceiling:.2f})",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("cost_ceiling_check_failed", error=str(exc))


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
    session_id: str | None = None
    collection: str = "default"


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


def _save_assistant_reply(
    convo: ConversationManager, final: PrivateAIState
) -> None:
    assistant_msg = Message(
        role="assistant", content=final.draft_answer, created_at=datetime.now(UTC)
    )
    updated = final.model_copy(
        update={"messages": list(final.messages) + [assistant_msg]}
    )
    try:
        convo.save_session(updated)
    except Exception as exc:
        logger.warning("save_session_failed", error=str(exc))


# ---------------------------------------------------------------------------
# POST /chat — blocking (used by offline_eval.py and tests)
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

    _check_cost_ceiling(db)

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
        latency_ms = int((time.monotonic() - started_at) * 1000)
        _write_audit_log(
            db,
            user_id=str(current_user.id),
            session_id=session_id,
            query=body.question,
            trace_id=trace_id,
            latency_ms=latency_ms,
            k_retrieved=0,
            status="error",
        )
        raise HTTPException(status_code=500, detail="Pipeline error") from exc

    latency_ms = int((time.monotonic() - started_at) * 1000)
    _save_assistant_reply(convo, final)
    _write_audit_log(
        db,
        user_id=str(current_user.id),
        session_id=session_id,
        query=body.question,
        trace_id=final.trace_id,
        latency_ms=latency_ms,
        k_retrieved=len(final.retrieved_chunks),
        status="completed",
    )
    # Rough token estimation: ~0.75 tokens / word (heuristic for English text)
    prompt_words = len(body.question.split())
    completion_words = len((final.draft_answer or "").split())
    _record_cost(db, session_id, int(prompt_words * 0.75), int(completion_words * 0.75))

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

    _check_cost_ceiling(db)

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
                    if isinstance(node_state, PrivateAIState):
                        final = node_state
                    elif isinstance(node_state, dict):
                        final = PrivateAIState(**node_state)

            # Close last step
            if active_step:
                yield _sse("step", {"name": active_step, "state": "done", "t": 0})

        except Exception as exc:
            logger.error("graph_stream_failed", error=str(exc))
            yield _sse("done", {"error": str(exc), "traceId": trace_id, "sessionId": session_id})
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
            })

        latency_ms = int((time.monotonic() - started_at) * 1000)
        try:
            _save_assistant_reply(convo, final)
            _write_audit_log(
                db,
                user_id=str(current_user.id),
                session_id=session_id,
                query=body.question,
                trace_id=final.trace_id,
                latency_ms=latency_ms,
                k_retrieved=len(final.retrieved_chunks),
                status="completed",
            )
            prompt_words = len(body.question.split())
            completion_words = len((final.draft_answer or "").split())
            _record_cost(db, session_id, int(prompt_words * 0.75), int(completion_words * 0.75))
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat_stream_postprocessing_failed", error=str(exc), trace_id=final.trace_id)
        yield _sse("done", {
            "traceId": final.trace_id,
            "latencyMs": latency_ms,
            "cache": False,
            "model": "local",
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
