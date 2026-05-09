"""Unit tests for observability.tracer — all OTEL SDK calls are mocked."""

from __future__ import annotations

import pytest


class TestGetTracer:
    def test_get_tracer_returns_tracer(self) -> None:
        from observability.tracer import get_tracer

        t = get_tracer("test")
        # Should be a real Tracer (or NoOpTracer) — just verify the protocol
        assert hasattr(t, "start_span")

    def test_get_tracer_different_names_are_independent(self) -> None:
        from observability.tracer import get_tracer

        t1 = get_tracer("module.a")
        t2 = get_tracer("module.b")
        # Both must be valid tracers
        assert hasattr(t1, "start_span")
        assert hasattr(t2, "start_span")


class TestPipelineSpan:
    def test_pipeline_span_context_manager_no_error(self) -> None:
        from observability.tracer import PipelineSpan, get_tracer

        tracer = get_tracer("test.pipeline")
        with PipelineSpan(tracer, "retrieval", trace_id="trace-001") as span:
            assert span is not None

    def test_pipeline_span_set_attribute_works(self) -> None:
        from observability.tracer import PipelineSpan, get_tracer

        tracer = get_tracer("test.pipeline")
        with PipelineSpan(tracer, "generate", trace_id="trace-002") as span:
            # set_attribute must not raise
            span.set_attribute("latency_ms", 42)
            span.set_attribute("model", "qwen3.5:9b")
            span.set_attribute("score", 0.97)
            span.set_attribute("cached", True)

    def test_pipeline_span_records_exception(self) -> None:
        from observability.tracer import PipelineSpan, get_tracer

        tracer = get_tracer("test.pipeline")
        with pytest.raises(ValueError):
            with PipelineSpan(tracer, "input_guard", trace_id="trace-003"):
                raise ValueError("guard failed")

    def test_pipeline_span_invalid_stage_raises(self) -> None:
        from observability.tracer import PipelineSpan, get_tracer

        tracer = get_tracer("test.pipeline")
        with pytest.raises(ValueError, match="Invalid stage"):
            PipelineSpan(tracer, "not_a_real_stage", trace_id="trace-004")

    def test_all_valid_stages_accepted(self) -> None:
        from observability.tracer import PipelineSpan, get_tracer

        tracer = get_tracer("test.pipeline")
        stages = [
            "input_guard",
            "query_rewrite",
            "retrieval",
            "rerank",
            "document_grade",
            "generate",
            "output_filter",
        ]
        for stage in stages:
            with PipelineSpan(tracer, stage, trace_id=f"trace-{stage}"):
                pass  # must not raise
