from __future__ import annotations

import os
from types import TracebackType

import structlog
from opentelemetry import context, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = structlog.get_logger(__name__)

_VALID_STAGES: frozenset[str] = frozenset(
    {
        "pipeline",
        "input_guard",
        "query_rewrite",
        "retrieval",
        "rerank",
        "document_grade",
        "generate",
        "output_filter",
    }
)

_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
_insecure = os.environ.get("OTEL_EXPORTER_INSECURE", "true").lower() == "true"
_exporter = OTLPSpanExporter(endpoint=_endpoint, insecure=_insecure)
_provider = TracerProvider()
_provider.add_span_processor(BatchSpanProcessor(_exporter))
trace.set_tracer_provider(_provider)


class PipelineSpan:
    """Context manager for a single pipeline stage span."""

    def __init__(self, tracer: trace.Tracer, stage: str, trace_id: str) -> None:
        if stage not in _VALID_STAGES:
            raise ValueError(f"Invalid stage '{stage}'. Must be one of: {sorted(_VALID_STAGES)}")
        self._tracer = tracer
        self._stage = stage
        self._trace_id = trace_id
        self._span: trace.Span | None = None
        self._token: object | None = None

    def __enter__(self) -> PipelineSpan:
        self._span = self._tracer.start_span(self._stage)
        self._span.set_attribute("trace_id", self._trace_id)
        self._span.set_attribute("stage", self._stage)
        ctx = trace.set_span_in_context(self._span)
        self._token = context.attach(ctx)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._token is not None:
            context.detach(self._token)  # type: ignore[arg-type]
        if self._span is not None:
            if exc_val is not None:
                self._span.record_exception(exc_val)
            self._span.end()

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        if self._span is not None:
            self._span.set_attribute(key, value)


def get_tracer(name: str) -> trace.Tracer:
    """Return an OpenTelemetry Tracer for the given instrumentation scope name."""
    return trace.get_tracer(name)
