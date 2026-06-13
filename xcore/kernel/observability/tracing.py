"""
tracing.py — Tracing interface: noop by default, real OpenTelemetry when configured.

Two backends:
- "noop"          : in-memory Tracer, no export (default, zero deps)
- "opentelemetry" : wraps OTel SDK, exports via OTLP to endpoint

Context propagation uses a ContextVar so that trace_id flows automatically
across async calls, including Plugin A → supervisor.call() → Plugin B.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:
    from ...configurations.sections import TracingConfig

# Current active span context — propagated across async boundaries automatically.
_current_trace_id: ContextVar[str | None] = ContextVar("xcore_trace_id", default=None)
_current_span_id: ContextVar[str | None] = ContextVar("xcore_span_id", default=None)


@dataclass
class Span:
    """Span de tracing."""

    name: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: str | None = None
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        self.end_time = time.monotonic()

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000


class Tracer:
    """Noop tracer — in-memory, zero export. Propagates trace_id via ContextVar."""

    def __init__(self, service_name: str = "xcore") -> None:
        self.service_name = service_name
        self._spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attrs) -> Generator[Span, None, None]:
        parent_trace_id = _current_trace_id.get()
        parent_span_id = _current_span_id.get()

        # Continue existing trace or start a new one
        trace_id = parent_trace_id or uuid.uuid4().hex
        s = Span(
            name=name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            attributes=attrs,
        )

        tok_trace = _current_trace_id.set(trace_id)
        tok_span = _current_span_id.set(s.span_id)
        try:
            yield s
        except Exception as e:
            s.set_status("error")
            s.set_attribute("error.message", str(e))
            raise
        finally:
            s.end()
            self._spans.append(s)
            _current_trace_id.reset(tok_trace)
            _current_span_id.reset(tok_span)

    def export(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "trace_id": s.trace_id,
                "span_id": s.span_id,
                "parent_span_id": s.parent_span_id,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "attributes": s.attributes,
            }
            for s in self._spans
        ]


class OtelTracer(Tracer):
    """
    OpenTelemetry-backed tracer.

    Wraps the OTel SDK so the rest of the codebase keeps using the same
    Tracer.span() interface. Exports spans via OTLP (gRPC or HTTP) to
    the configured endpoint.

    Requires:
        opentelemetry-sdk
        opentelemetry-exporter-otlp-proto-grpc  (or -http)
    """

    def __init__(self, service_name: str, endpoint: str, use_grpc: bool = True) -> None:
        super().__init__(service_name)
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource(attributes={SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        if use_grpc:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=endpoint)
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=endpoint)

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        self._otel_tracer = trace.get_tracer(service_name)
        self._provider = provider

    @contextmanager
    def span(self, name: str, **attrs) -> Generator[Span, None, None]:
        # from opentelemetry import context as otel_context
        from opentelemetry import trace

        parent_trace_id = _current_trace_id.get()
        parent_span_id = _current_span_id.get()

        with self._otel_tracer.start_as_current_span(name) as otel_span:
            for k, v in attrs.items():
                otel_span.set_attribute(k, str(v))

            otel_ctx = otel_span.get_span_context()
            trace_id = (
                format(otel_ctx.trace_id, "032x")
                if otel_ctx.is_valid
                else (parent_trace_id or uuid.uuid4().hex)
            )
            span_id_hex = (
                format(otel_ctx.span_id, "016x")
                if otel_ctx.is_valid
                else uuid.uuid4().hex[:16]
            )

            s = Span(
                name=name,
                trace_id=trace_id,
                span_id=span_id_hex,
                parent_span_id=parent_span_id,
                attributes=dict(attrs),
            )

            tok_trace = _current_trace_id.set(trace_id)
            tok_span = _current_span_id.set(span_id_hex)
            try:
                yield s
            except Exception as e:
                s.set_status("error")
                s.set_attribute("error.message", str(e))
                otel_span.set_status(trace.StatusCode.ERROR, description=str(e))
                raise
            finally:
                s.end()
                for k, v in s.attributes.items():
                    otel_span.set_attribute(k, str(v))
                _current_trace_id.reset(tok_trace)
                _current_span_id.reset(tok_span)

    def shutdown(self) -> None:
        self._provider.shutdown()


def create_tracer(config: "TracingConfig") -> Tracer:
    """
    Factory — returns the right Tracer based on integration.yaml config.

    observability:
      tracing:
        enabled: true
        backend: opentelemetry   # "noop" | "opentelemetry"
        service_name: my-service
        endpoint: http://otel-collector:4317   # gRPC
        # endpoint: http://otel-collector:4318/v1/traces  # HTTP
        use_grpc: true
    """
    if not config.enabled or config.backend == "noop":
        return Tracer(config.service_name)

    if config.backend == "opentelemetry":
        if not config.endpoint:
            raise ValueError("tracing.endpoint is required when backend=opentelemetry")
        try:
            use_grpc = getattr(config, "use_grpc", True)
            return OtelTracer(
                service_name=config.service_name,
                endpoint=config.endpoint,
                use_grpc=use_grpc,
            )
        except ImportError as e:
            raise ImportError(
                "opentelemetry packages required for backend=opentelemetry. "
                "Install: opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc"
            ) from e

    raise ValueError(
        f"Unknown tracing backend: {config.backend!r}. "
        "Valid values: 'noop', 'opentelemetry'"
    )


def noop_tracer() -> Tracer:
    return Tracer("noop")


def get_current_trace_id() -> str | None:
    return _current_trace_id.get()


def get_current_span_id() -> str | None:
    return _current_span_id.get()
