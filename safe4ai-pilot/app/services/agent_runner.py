from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import HumanReviewQueue
from app.models import PrivateAIState
from app.services.conversation import ConversationManager
from observability.tracer import PipelineSpan, get_tracer


async def run_agent_query(
    state: PrivateAIState,
    graph: Any,
    *,
    db: Session,
    conversation_manager: ConversationManager,
) -> PrivateAIState:
    """Run the graph, save session state, and insert human review queue entry if needed.

    This wrapper owns all DB side-effects so graph nodes stay pure.
    The tracer span covers the full pipeline from intake to respond/fallback.
    """
    if not state.trace_id:
        state = state.model_copy(update={"trace_id": str(uuid.uuid4())})
    tracer = get_tracer("safe4ai.graph")
    with PipelineSpan(tracer, "pipeline", state.trace_id) as span:
        span.set_attribute("session_id", state.session_id)
        span.set_attribute("user_id", state.user_id)
        result = await graph.ainvoke(state)

    final_state = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)

    # Save session: corresponds to the "save at respond/fallback" requirement
    conversation_manager.save_session(final_state)

    # Human review queue insertion
    if final_state.requires_human_review:
        query = final_state.messages[-1].content if final_state.messages else ""
        entry = HumanReviewQueue(
            id=str(uuid.uuid4()),
            session_id=final_state.session_id,
            user_id=final_state.user_id,
            query=query[:500],
            draft_answer=final_state.draft_answer or None,
            citations_json=[c.model_dump() for c in final_state.citations],
            risk_reason="Automatic flagging: low retrieval quality or output blocked",
        )
        db.add(entry)
        db.commit()

    return final_state
