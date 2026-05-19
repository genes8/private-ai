"""Integration tests for Phase 3A: LangGraph agent workflow and supporting components."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock  # noqa: F401 (AsyncMock used in mocks)

import httpx
import pytest

from app.agents.adaptive_router import route_after_grade, route_quality_gate
from app.agents.document_grader import grade_chunks
from app.agents.query_decomposer import decompose_query
from app.models import GradedChunk, Message, PrivateAIState, RankedChunk

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ranked_chunk(**overrides: Any) -> RankedChunk:
    defaults: dict[str, Any] = {
        "chunk_id": "c1",
        "doc_id": "d1",
        "filename": "policy.pdf",
        "page_number": 1,
        "content": "Employees are entitled to 20 days of annual leave.",
        "score": 0.9,
        "rerank_score": 0.8,
    }
    defaults.update(overrides)
    return RankedChunk(**defaults)


def _make_graded_chunk(relevant: bool, **overrides: Any) -> GradedChunk:
    ranked_fields = set(RankedChunk.model_fields)
    base = _make_ranked_chunk(**{k: v for k, v in overrides.items() if k in ranked_fields})
    reason = "ok" if relevant else "off topic"
    return GradedChunk(**base.model_dump(), relevant=relevant, reason=reason)


def _make_state(**overrides: Any) -> PrivateAIState:
    defaults: dict[str, Any] = {
        "session_id": "sess-1",
        "user_id": "user-1",
        "messages": [Message(role="user", content="How many leave days do employees get?")],
    }
    defaults.update(overrides)
    return PrivateAIState(**defaults)


def _smart_ollama_handler(
    *,
    grade_relevant: bool = True,
    grade_decision: str = "generate",
    quality_gate_decision: str = "respond",
    answer: str = "Employees get 20 days of annual leave.",
    decompose_sub_queries: list[str] | None = None,
) -> Any:
    """Build a handler that dispatches on prompt template keywords."""
    sub_queries = decompose_sub_queries or ["What is the leave policy?"]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt: str = body.get("prompt", "")

        if "search query optimizer" in prompt:
            return httpx.Response(200, json={"response": "refined query"})
        if "grading whether a document chunk" in prompt:
            reason = "ok" if grade_relevant else "off topic"
            payload = {"relevant": grade_relevant, "reason": reason}
            return httpx.Response(200, json={"response": json.dumps(payload)})
        if "simpler sub-questions" in prompt:
            return httpx.Response(200, json={"response": json.dumps({"sub_queries": sub_queries})})
        if "pipeline router" in prompt and "Current step: quality_gate" in prompt:
            body_out = json.dumps({"decision": quality_gate_decision})
            return httpx.Response(200, json={"response": body_out})
        if "pipeline router" in prompt:
            return httpx.Response(200, json={"response": json.dumps({"decision": grade_decision})})
        if "Answer the following question" in prompt:
            return httpx.Response(200, json={"response": answer})
        return httpx.Response(200, json={"response": ""})

    return handler


def _build_graph(handler: Any, *, chunks: list[RankedChunk] | None = None) -> Any:
    from app.agents.graph import build_graph
    from app.components.hybrid_retriever import HybridRetriever
    from app.components.reranker import Reranker

    two_chunks = chunks or [_make_ranked_chunk(), _make_ranked_chunk(chunk_id="c2")]
    retriever = MagicMock(spec=HybridRetriever)
    retriever.retrieve = AsyncMock(return_value=two_chunks)

    reranker = MagicMock(spec=Reranker)
    reranker.rerank.return_value = two_chunks

    transport = httpx.MockTransport(handler=handler)
    client = httpx.AsyncClient(transport=transport)

    graph = build_graph(
        retriever=retriever,
        reranker=reranker,
        ollama_url="http://mock",
        ollama_model="test",
        http_client=client,
    )
    return graph, client


# ---------------------------------------------------------------------------
# Scenario 1: Single-turn Q&A → grounded answer with citations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_single_turn_grounded_answer() -> None:
    graph, client = _build_graph(
        _smart_ollama_handler(
            grade_relevant=True,
            grade_decision="generate",
            quality_gate_decision="respond",
            answer="Employees get 20 days annual leave.",
        )
    )
    async with client:
        state = _make_state()
        result = await graph.ainvoke(state)

    final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
    assert final.grounded is True
    assert final.draft_answer == "Employees get 20 days annual leave."
    assert len(final.citations) > 0
    assert final.status == "completed"


# ---------------------------------------------------------------------------
# Scenario 2: Out-of-scope question → fallback, no hallucination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_out_of_scope_goes_to_fallback() -> None:
    low_score_chunks = [
        _make_ranked_chunk(rerank_score=0.1),
        _make_ranked_chunk(chunk_id="c2", rerank_score=0.2),
    ]
    graph, client = _build_graph(
        _smart_ollama_handler(
            grade_relevant=False,
            grade_decision="decompose",
            quality_gate_decision="fallback",
        ),
        chunks=low_score_chunks,
    )
    async with client:
        state = _make_state(
            messages=[Message(role="user", content="What is the weather on Mars?")]
        )
        result = await graph.ainvoke(state)

    final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
    assert final.grounded is False
    assert final.status == "completed"
    assert final.current_step == "fallback"


# ---------------------------------------------------------------------------
# Scenario 3: < 2 relevant chunks → decomposer triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_decomposer_triggers_when_few_relevant_chunks() -> None:
    graph, client = _build_graph(
        _smart_ollama_handler(
            grade_relevant=False,
            grade_decision="decompose",
            quality_gate_decision="fallback",
            decompose_sub_queries=["What is leave policy?", "How many vacation days?"],
        ),
        chunks=[
            _make_ranked_chunk(rerank_score=0.9),
            _make_ranked_chunk(chunk_id="c2", rerank_score=0.2),
        ],
    )
    async with client:
        state = _make_state(
            messages=[Message(role="user", content="Tell me about leave and benefits policy.")]
        )
        result = await graph.ainvoke(state)

    final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
    assert len(final.sub_queries) > 0


# ---------------------------------------------------------------------------
# Scenario 4: Not grounded → self-correction → retrieve → loop guard cuts off
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_answer_with_no_relevant_chunks_does_not_self_correct() -> None:
    """No relevant chunks already produce a final fallback; do not retrieve/rerank again."""
    def stateful_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt: str = body.get("prompt", "")

        if "search query optimizer" in prompt:
            return httpx.Response(200, json={"response": "refined query"})
        if "simpler sub-questions" in prompt:
            return httpx.Response(200, json={"response": json.dumps({"sub_queries": ["sub-q"]})})
        if "grading whether a document chunk" in prompt or "pipeline router" in prompt:
            return httpx.Response(500, json={"error": "unexpected LLM call"})
        return httpx.Response(200, json={"response": ""})

    graph, client = _build_graph(
        stateful_handler,
        chunks=[
            _make_ranked_chunk(rerank_score=0.1),
            _make_ranked_chunk(chunk_id="c2", rerank_score=0.2),
        ],
    )
    async with client:
        state = _make_state()
        result = await graph.ainvoke(state)

    final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
    assert final.retrieval_attempts == 1
    assert final.current_step == "fallback"
    assert final.status == "completed"


# ---------------------------------------------------------------------------
# Scenario 5: LLM error → caught, logged, user-friendly error returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_llm_error_graceful_degradation() -> None:
    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal server error"})

    graph, client = _build_graph(error_handler)
    async with client:
        state = _make_state()
        result = await graph.ainvoke(state)

    final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
    # Graph must not crash; final state should be a terminal step
    assert final.status == "completed"
    assert final.current_step in {"respond", "fallback"}


# ---------------------------------------------------------------------------
# Scenario 6: requires_human_review → run_agent_query inserts queue entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_human_review_queue_inserted() -> None:
    from app.services.agent_runner import run_agent_query

    mock_graph = MagicMock()
    final_state = _make_state(
        requires_human_review=True,
        draft_answer="Some answer",
        status="completed",
        current_step="fallback",
    )
    mock_graph.ainvoke = AsyncMock(return_value=final_state)

    mock_db = MagicMock()
    mock_conv_mgr = MagicMock()
    mock_conv_mgr.save_session = MagicMock()

    await run_agent_query(
        final_state,
        mock_graph,
        db=mock_db,
        conversation_manager=mock_conv_mgr,
    )

    mock_conv_mgr.save_session.assert_called_once()
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 7: 15-turn session → summarization triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_long_session_triggers_summarization() -> None:
    from app.services.conversation import ConversationManager

    messages_15 = [
        Message(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")
        for i in range(15)
    ]
    full_state = _make_state(messages=messages_15)

    mock_db = MagicMock()
    mock_db.get.return_value = MagicMock(state_json=full_state.model_dump())

    conv_mgr = ConversationManager(mock_db)

    def summarize_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt: str = body.get("prompt", "")
        if "Summarize the following conversation" in prompt:
            return httpx.Response(200, json={"response": "Summary of 15 messages."})
        return httpx.Response(200, json={"response": ""})

    transport = httpx.MockTransport(handler=summarize_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await conv_mgr.maybe_summarize(
            "sess-1",
            ollama_url="http://mock",
            model="test",
            client=client,
        )

    # save_session was called (mock_db.get for save → mock_db object)
    mock_db.commit.assert_called()
    # The saved state should have only 1 message (the summary)
    saved_state_json = mock_db.get.return_value.state_json
    if isinstance(saved_state_json, dict):
        saved_msgs = saved_state_json.get("messages", messages_15)
        assert len(saved_msgs) < len(messages_15)


# ---------------------------------------------------------------------------
# Additional unit tests for routing threshold and graph compilation
# ---------------------------------------------------------------------------


def test_node_span_parented_under_pipeline_span(monkeypatch: pytest.MonkeyPatch) -> None:
    """OTel child span from _node_span must have pipeline span as its parent."""
    # OTEL_SDK_DISABLED is set globally in pytest env to suppress noise; disable it here
    # so the freshly-created TracerProvider produces real (recording) spans.
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)

    from unittest.mock import patch

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from app.agents.graph import _node_span

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    pipeline_tracer = provider.get_tracer("pipeline")
    node_tracer = provider.get_tracer("nodes")

    state = _make_state()
    with patch("app.agents.graph._node_tracer", node_tracer):
        with pipeline_tracer.start_as_current_span("pipeline"):
            with _node_span("intake", state):
                pass

    spans = exporter.get_finished_spans()
    pipeline_s = next(s for s in spans if s.name == "pipeline")
    intake_s = next(s for s in spans if s.name == "intake")

    assert intake_s.parent is not None
    assert intake_s.parent.span_id == pipeline_s.context.span_id


@pytest.mark.asyncio
async def test_generation_context_captured_in_final_state() -> None:
    """generate_node must snapshot the relevant chunks into generation_context."""
    graph, client = _build_graph(
        _smart_ollama_handler(
            grade_relevant=True,
            grade_decision="generate",
            quality_gate_decision="respond",
            answer="Employees get 20 days annual leave.",
        )
    )
    async with client:
        state = _make_state()
        result = await graph.ainvoke(state)

    final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
    assert len(final.generation_context) > 0, "generation_context must be set after generation"
    assert all(c.relevant for c in final.generation_context), "only relevant chunks in context"


class TestRoutingThreshold:
    def test_route_after_grade_two_relevant_goes_to_generate(self) -> None:
        chunks = [_make_graded_chunk(True), _make_graded_chunk(True)]
        state = _make_state(graded_chunks=chunks)
        assert route_after_grade(state) == "generate"

    def test_route_after_grade_one_relevant_goes_to_decompose(self) -> None:
        chunks = [_make_graded_chunk(True), _make_graded_chunk(False)]
        state = _make_state(graded_chunks=chunks)
        assert route_after_grade(state) == "decompose"

    def test_route_after_grade_no_relevant_goes_to_decompose(self) -> None:
        state = _make_state(graded_chunks=[_make_graded_chunk(False)])
        assert route_after_grade(state) == "decompose"

    def test_route_quality_gate_grounded_goes_to_respond(self) -> None:
        state = _make_state(grounded=True)
        assert route_quality_gate(state) == "respond"

    def test_route_quality_gate_not_grounded_goes_to_fallback(self) -> None:
        state = _make_state(grounded=False)
        assert route_quality_gate(state) == "fallback"


class TestRuntimeSafety:
    def test_session_state_is_json_serializable(self) -> None:
        """model_dump(mode='json') must not raise TypeError on datetime fields."""
        import json as _json

        state = _make_state()
        dumped = state.model_dump(mode="json")
        _json.dumps(dumped)  # must not raise

    @pytest.mark.asyncio
    async def test_ungrounded_answer_never_routes_to_respond(self) -> None:
        """When LLM maliciously returns 'respond' but state is not grounded → fallback."""

        def bad_router(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            prompt: str = body.get("prompt", "")
            if "search query optimizer" in prompt:
                return httpx.Response(200, json={"response": "refined"})
            if "grading whether a document chunk" in prompt:
                payload = {"relevant": False, "reason": "off topic"}
                return httpx.Response(200, json={"response": json.dumps(payload)})
            if "simpler sub-questions" in prompt:
                return httpx.Response(200, json={"response": json.dumps({"sub_queries": ["q"]})})
            if "pipeline router" in prompt:
                # LLM incorrectly returns "respond" even though answer is ungrounded
                return httpx.Response(200, json={"response": json.dumps({"decision": "respond"})})
            if "Answer the following question" in prompt:
                return httpx.Response(200, json={"response": ""})
            return httpx.Response(200, json={"response": ""})

        graph, client = _build_graph(bad_router)
        async with client:
            result = await graph.ainvoke(_make_state())

        final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
        assert final.current_step == "fallback", "ungrounded state must never reach respond"
        assert final.grounded is False

    @pytest.mark.asyncio
    async def test_no_relevant_chunks_route_to_decompose_without_grade_router(self) -> None:
        """0 score-relevant chunks → sync route_after_grade → decompose."""

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            prompt: str = body.get("prompt", "")
            if "search query optimizer" in prompt:
                return httpx.Response(200, json={"response": "refined"})
            if "simpler sub-questions" in prompt:
                return httpx.Response(200, json={"response": json.dumps({"sub_queries": ["sub"]})})
            if "grading whether a document chunk" in prompt or "pipeline router" in prompt:
                return httpx.Response(500, json={"error": "unexpected LLM call"})
            return httpx.Response(200, json={"response": ""})

        graph, client = _build_graph(
            handler,
            chunks=[
                _make_ranked_chunk(rerank_score=0.1),
                _make_ranked_chunk(chunk_id="c2", rerank_score=0.2),
            ],
        )
        async with client:
            result = await graph.ainvoke(_make_state())

        final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
        assert len(final.sub_queries) > 0, "decompose must run when score grading finds no relevant chunks"
        assert final.status == "completed"

    @pytest.mark.asyncio
    async def test_errors_in_fallback_set_requires_human_review(self) -> None:
        """Retrieval failure → fallback with errors → requires_human_review = True."""
        from app.agents.graph import build_graph
        from app.components.hybrid_retriever import HybridRetriever
        from app.components.reranker import Reranker

        retriever = MagicMock(spec=HybridRetriever)
        retriever.retrieve = AsyncMock(side_effect=RuntimeError("qdrant down"))
        reranker = MagicMock(spec=Reranker)

        transport = httpx.MockTransport(handler=lambda r: httpx.Response(500))
        async with httpx.AsyncClient(transport=transport) as client:
            graph = build_graph(
                retriever=retriever,
                reranker=reranker,
                ollama_url="http://mock",
                ollama_model="test",
                http_client=client,
            )
            result = await graph.ainvoke(_make_state())

        final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
        assert final.requires_human_review is True

    @pytest.mark.asyncio
    async def test_graph_uses_score_grading_and_sync_routing_without_extra_llm_calls(self) -> None:
        from app.agents.graph import build_graph
        from app.components.hybrid_retriever import HybridRetriever
        from app.components.reranker import Reranker

        requests: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            prompt: str = body.get("prompt", "")
            requests.append(prompt)
            if "search query optimizer" in prompt:
                return httpx.Response(200, json={"response": "refined query"})
            if "Answer the following question" in prompt:
                return httpx.Response(200, json={"response": "Evidence-backed answer."})
            return httpx.Response(500)

        retriever = MagicMock(spec=HybridRetriever)
        retriever.retrieve = AsyncMock(
            return_value=[
                _make_ranked_chunk(chunk_id="c1", rerank_score=0.9),
                _make_ranked_chunk(chunk_id="c2", rerank_score=0.8),
            ]
        )
        reranker = MagicMock(spec=Reranker)
        reranker.rerank.return_value = retriever.retrieve.return_value

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            graph = build_graph(
                retriever=retriever,
                reranker=reranker,
                ollama_url="http://mock",
                ollama_model="test",
                http_client=client,
            )
            result = await graph.ainvoke(_make_state())

        final = result if isinstance(result, PrivateAIState) else PrivateAIState(**result)
        assert final.status == "completed"
        assert final.current_step == "respond"
        assert final.draft_answer == "Evidence-backed answer."
        assert len(requests) == 2
        assert any("search query optimizer" in prompt for prompt in requests)
        assert any("Answer the following question" in prompt for prompt in requests)
        assert not any("grading whether a document chunk" in prompt for prompt in requests)
        assert not any("pipeline router" in prompt for prompt in requests)


class TestComponentUnit:
    @pytest.mark.asyncio
    async def test_grade_chunks_returns_irrelevant_on_500(self) -> None:
        chunk = _make_ranked_chunk()
        transport = httpx.MockTransport(handler=lambda r: httpx.Response(500))
        async with httpx.AsyncClient(transport=transport) as client:
            results = await grade_chunks(
                "query", [chunk], ollama_url="http://mock", model="test", client=client
            )
        assert results[0].relevant is False
        assert results[0].reason == "grading failed"

    @pytest.mark.asyncio
    async def test_decompose_query_returns_original_on_500(self) -> None:
        transport = httpx.MockTransport(handler=lambda r: httpx.Response(500))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await decompose_query(
                "complex question", ollama_url="http://mock", model="test", client=client
            )
        assert result == ["complex question"]

    def test_build_graph_compiles(self) -> None:
        from app.agents.graph import build_graph
        from app.components.hybrid_retriever import HybridRetriever
        from app.components.reranker import Reranker

        graph = build_graph(
            retriever=MagicMock(spec=HybridRetriever),
            reranker=MagicMock(spec=Reranker),
            ollama_url="http://mock",
            ollama_model="test",
        )
        assert hasattr(graph, "ainvoke")
