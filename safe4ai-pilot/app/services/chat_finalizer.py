from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import AgentRun, AuditLog
from app.db.models import Session as DbSession
from app.models import Message, PrivateAIState
from app.services.provider_clients import ProviderUsage


def finalize_chat_run(
    *,
    db: Session,
    final: PrivateAIState,
    user_id: str,
    query: str,
    latency_ms: int,
    k_retrieved: int,
    usage: ProviderUsage,
    cost_per_1k_tokens: float,
) -> None:
    """Persist assistant reply, audit log, and cost record in a single transaction."""
    assistant_msg = Message(role="assistant", content=final.draft_answer, created_at=datetime.now(UTC))
    updated = final.model_copy(update={"messages": list(final.messages) + [assistant_msg]})
    cost_usd = usage.total_tokens / 1000.0 * cost_per_1k_tokens
    now = datetime.now(UTC)

    with db.begin():
        row = db.get(DbSession, final.session_id)
        if row is not None:
            row.state_json = updated.model_dump(mode="json")
            row.updated_at = now

        db.add(
            AuditLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=final.session_id,
                action_type="chat_query",
                query_text=query[:500],
                response_metadata={
                    "trace_id": final.trace_id,
                    "k_retrieved": k_retrieved,
                    "status": "completed",
                    "usage_source": usage.source,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
                latency_ms=latency_ms,
                model_used=final.trace_id,
                trace_id=final.trace_id,
            )
        )
        db.add(
            AgentRun(
                id=str(uuid.uuid4()),
                session_id=final.session_id,
                started_at=now,
                finished_at=now,
                status="completed",
                cost_usd=cost_usd,
                final_output=None,
                error=None,
            )
        )
