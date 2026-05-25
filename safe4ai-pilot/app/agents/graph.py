from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

import httpx
import structlog
from langgraph.graph import END, StateGraph
from opentelemetry import trace as otel_trace

from app.agents.adaptive_router import route_after_grade, route_quality_gate
from app.agents.document_grader import grade_chunks
from app.agents.llm_caller import call_llm
from app.agents.query_decomposer import decompose_query
from app.components.hybrid_retriever import HybridRetriever
from app.components.reranker import Reranker
from app.models import Citation, GradedChunk, PrivateAIState, RankedChunk
from app.prompts.registry import get_prompt
from app.security.input_guard import InputGuard
from app.security.output_filter import OutputFilter

logger = structlog.get_logger(__name__)

_node_tracer = otel_trace.get_tracer("safe4ai.graph.nodes")


@contextlib.contextmanager
def _node_span(name: str, state: PrivateAIState) -> Generator[otel_trace.Span, None, None]:
    """Child span for a single graph node. Inherits context from the parent pipeline span."""
    with _node_tracer.start_as_current_span(name) as span:
        span.set_attribute("session_id", state.session_id)
        span.set_attribute("trace_id", state.trace_id)
        span.set_attribute("node", name)
        yield span

_NO_ANSWER = "I don't have enough information in the provided documents to answer this question."

# Max retrieve passes before the self-correction loop is cut off
_MAX_RETRIEVAL_ATTEMPTS = 2


def build_graph(
    *,
    retriever: HybridRetriever,
    reranker: Reranker,
    chat_client: Any = None,
    ollama_url: str | None = None,
    ollama_model: str | None = None,
    retrieval_top_k: int = 6,
    rerank_threshold: float = 0.45,
    http_client: httpx.AsyncClient | None = None,
) -> Any:
    """Build and compile the LangGraph StateGraph for the RAG pipeline."""
    guard = InputGuard()
    output_filter = OutputFilter()

    # Resolve fallback Ollama coordinates for nodes that don't yet use chat_client
    _ollama_url = ollama_url or ""
    _ollama_model = ollama_model or ""

    async def intake_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("intake", state):
            if not state.messages:
                return {"current_step": "fallback", "errors": ["No messages in state"]}
            query = state.messages[-1].content
            result = guard.check(query)
            if not result.allowed:
                return {
                    "current_step": "fallback",
                    "errors": state.errors + [result.reason],
                }
            return {"current_step": "rewrite"}

    async def rewrite_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("rewrite", state):
            query = state.messages[-1].content if state.messages else ""
            template = get_prompt("query_rewriter", "v1")
            # Include up to last 3 prior exchanges so follow-up questions resolve correctly.
            prior = state.messages[:-1][-6:]  # up to 6 messages = 3 user+assistant pairs
            if prior:
                history = "".join(
                    f"{m.role.capitalize()}: {m.content}\n" for m in prior
                ) + "\n"
            else:
                history = ""
            prompt = template.template.format(query=query, history=history)
            try:
                rewritten = await call_llm(
                    prompt,
                    chat_client=chat_client,
                    ollama_url=_ollama_url,
                    model=_ollama_model,
                    http_client=http_client,
                )
                return {"rewritten_query": rewritten.strip() or query, "current_step": "retrieve"}
            except Exception as exc:
                logger.warning("rewrite_node_failed", error=str(exc), exc_type=type(exc).__name__)
                return {"rewritten_query": query, "current_step": "retrieve"}

    async def retrieve_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("retrieve", state) as span:
            query = state.rewritten_query or (state.messages[-1].content if state.messages else "")
            effective_top_k = retrieval_top_k + state.retrieval_attempts * 4
            try:
                raw_chunks = await retriever.retrieve(query, top_k=effective_top_k)
                ranked: list[RankedChunk] = await reranker.arerank(query, raw_chunks, top_n=effective_top_k)
                max_score = max((c.rerank_score for c in ranked), default=0.0)
                span.set_attribute("chunk_count", len(ranked))
                return {
                    "retrieved_chunks": ranked,
                    "retrieval_score_max": max_score,
                    "retrieval_attempts": state.retrieval_attempts + 1,
                    "current_step": "grade",
                }
            except Exception as exc:
                span.record_exception(exc)
                return {
                    "retrieval_attempts": state.retrieval_attempts + 1,
                    "current_step": "grade",
                    "errors": state.errors + [str(exc)],
                }

    async def grade_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("grade", state) as span:
            query = state.rewritten_query or (state.messages[-1].content if state.messages else "")
            graded = await grade_chunks(
                query,
                state.retrieved_chunks,
                chat_client=chat_client,
                ollama_url=_ollama_url,
                model=_ollama_model,
                client=http_client,
                rerank_threshold=rerank_threshold,
            )
            relevant_count = sum(1 for c in graded if c.relevant)
            span.set_attribute("relevant_chunks", relevant_count)
            routing_state = state.model_copy(update={"graded_chunks": graded})
            decision = route_after_grade(routing_state)
            span.set_attribute("routing_decision", decision)
            return {"graded_chunks": graded, "current_step": decision}

    async def decompose_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("decompose", state) as span:
            query = state.rewritten_query or (state.messages[-1].content if state.messages else "")
            sub_queries = await decompose_query(
                query,
                chat_client=chat_client,
                ollama_url=_ollama_url,
                model=_ollama_model,
                client=http_client,
            )
            span.set_attribute("sub_query_count", len(sub_queries))

            all_graded: list[GradedChunk] = []
            for sub_q in sub_queries:
                try:
                    raw = await retriever.retrieve(sub_q, top_k=retrieval_top_k)
                    ranked: list[RankedChunk] = await reranker.arerank(sub_q, raw, top_n=min(3, retrieval_top_k))
                    graded = await grade_chunks(
                        sub_q,
                        ranked,
                        chat_client=chat_client,
                        ollama_url=_ollama_url,
                        model=_ollama_model,
                        client=http_client,
                        rerank_threshold=rerank_threshold,
                    )
                    all_graded.extend(graded)
                except Exception as exc:
                    logger.warning("decompose_sub_query_failed", sub_query=sub_q, error=str(exc))
                    continue

            needs_review = not any(c.relevant for c in all_graded)
            max_score = max((c.rerank_score for c in all_graded), default=0.0)
            return {
                "sub_queries": sub_queries,
                "graded_chunks": all_graded,
                "retrieval_score_max": max_score,
                "requires_human_review": needs_review,
                "current_step": "generate",
            }

    async def generate_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("generate", state):
            query = state.rewritten_query or (state.messages[-1].content if state.messages else "")
            relevant = [c for c in state.graded_chunks if c.relevant]

            if not relevant:
                return {
                    "draft_answer": _NO_ANSWER,
                    "citations": [],
                    "generation_context": [],
                    "current_step": "output_filter",
                }

            context = "\n\n".join(
                f"[{c.filename} p.{c.page_number}]: {c.content}" for c in relevant
            )
            template = get_prompt("rag_answer", "v1")
            prompt = template.template.format(context=context, query=query)

            try:
                provider_usage = None
                if chat_client is not None:
                    result = await chat_client.chat("", prompt)
                    answer = result.content.strip()
                    provider_usage = result.usage
                else:
                    answer = (await call_llm(
                        prompt,
                        ollama_url=_ollama_url,
                        model=_ollama_model,
                        http_client=http_client,
                        timeout=120.0,
                    )).strip()
            except Exception as exc:
                return {
                    "draft_answer": _NO_ANSWER,
                    "citations": [],
                    "errors": state.errors + [str(exc)],
                    "current_step": "output_filter",
                }

            citations = [
                Citation(
                    filename=c.filename,
                    page_number=c.page_number,
                    excerpt=c.content[:200],
                    score=c.rerank_score,
                )
                for c in relevant
            ]
            return {
                "draft_answer": answer,
                "citations": citations,
                "generation_context": relevant,
                "current_step": "output_filter",
                "provider_usage": provider_usage,
            }

    async def output_filter_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("output_filter", state):
            relevant = state.generation_context or [c for c in state.graded_chunks if c.relevant]
            if not relevant or not state.draft_answer or state.draft_answer == _NO_ANSWER:
                return {"current_step": "quality_gate"}
            ranked_fields = set(RankedChunk.model_fields)
            source_ranked = [
                RankedChunk(**{k: v for k, v in c.model_dump().items() if k in ranked_fields})
                for c in relevant
            ]
            guard_result = output_filter.check(state.draft_answer, source_ranked)
            if not guard_result.allowed:
                return {
                    "draft_answer": _NO_ANSWER,
                    "citations": [],
                    "requires_human_review": True,
                    "errors": state.errors + [guard_result.reason],
                    "current_step": "quality_gate",
                }
            return {"current_step": "quality_gate"}

    async def quality_gate_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("quality_gate", state) as span:
            has_relevant = any(c.relevant for c in state.graded_chunks)
            grounded = (
                bool(state.draft_answer)
                and state.draft_answer != _NO_ANSWER
                and has_relevant
            )
            if state.retrieval_attempts >= _MAX_RETRIEVAL_ATTEMPTS:
                allowed = ["respond", "fallback"]
            else:
                allowed = ["respond", "retrieve", "fallback"]

            routing_state = state.model_copy(update={"grounded": grounded})
            decision = route_quality_gate(routing_state)
            no_answer_without_context = state.draft_answer == _NO_ANSWER and not has_relevant
            if (
                state.retrieval_attempts < _MAX_RETRIEVAL_ATTEMPTS
                and not grounded
                and decision == "fallback"
                and not no_answer_without_context
            ):
                decision = "retrieve"
            span.set_attribute("grounded", grounded)
            span.set_attribute("routing_decision", decision)
            return {"grounded": grounded, "current_step": decision}

    async def respond_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("respond", state):
            return {"status": "completed", "current_step": "respond"}

    async def fallback_node(state: PrivateAIState) -> dict[str, Any]:
        with _node_span("fallback", state):
            answer = state.draft_answer or _NO_ANSWER
            return {
                "draft_answer": answer,
                "status": "completed",
                "current_step": "fallback",
                "requires_human_review": state.requires_human_review or bool(state.errors),
            }

    builder: StateGraph[PrivateAIState, PrivateAIState, PrivateAIState] = StateGraph(PrivateAIState)

    builder.add_node("intake", intake_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("grade", grade_node)
    builder.add_node("decompose", decompose_node)
    builder.add_node("generate", generate_node)
    builder.add_node("output_filter", output_filter_node)
    builder.add_node("quality_gate", quality_gate_node)
    builder.add_node("respond", respond_node)
    builder.add_node("fallback", fallback_node)

    builder.set_entry_point("intake")

    builder.add_conditional_edges(
        "intake",
        lambda state: state.current_step,
        {"rewrite": "rewrite", "fallback": "fallback"},
    )
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("retrieve", "grade")
    builder.add_conditional_edges(
        "grade",
        lambda state: state.current_step,
        {"generate": "generate", "decompose": "decompose"},
    )
    builder.add_edge("decompose", "generate")
    builder.add_edge("generate", "output_filter")
    builder.add_edge("output_filter", "quality_gate")
    builder.add_conditional_edges(
        "quality_gate",
        lambda state: state.current_step,
        {"respond": "respond", "retrieve": "retrieve", "fallback": "fallback"},
    )
    builder.add_edge("respond", END)
    builder.add_edge("fallback", END)

    return builder.compile()
