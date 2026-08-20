"""Tests for the OpenTelemetry-backed Tracer, context propagation and TraceContextMiddleware."""

import pytest


def _make_otel_tracer(service_name="svc-test"):
    from xcore.configurations.sections import TracingConfig
    from xcore.kernel.observability.tracing import Tracer

    return Tracer(service_name, TracingConfig(enabled=True, backend="opentelemetry"))


class TestOtelBackedTracer:
    def test_span_produces_real_otel_ids(self):
        tracer = _make_otel_tracer()
        with tracer.span("op") as span:
            pass
        # 128-bit trace_id (32 hex chars) / 64-bit span_id (16 hex chars),
        # non-null (all-zero would mean an invalid/no-op span context).
        assert len(span.trace_id) == 32
        assert len(span.span_id) == 16
        assert int(span.trace_id, 16) != 0
        assert int(span.span_id, 16) != 0

    def test_nested_spans_share_trace_id(self):
        tracer = _make_otel_tracer()
        with tracer.span("parent") as parent:
            with tracer.span("child") as child:
                pass
        assert child.trace_id == parent.trace_id
        assert child.span_id != parent.span_id

    def test_span_error_sets_otel_status(self):
        tracer = _make_otel_tracer()
        with pytest.raises(ValueError):
            with tracer.span("op") as span:
                raise ValueError("boom")
        assert span.status == "error"

    def test_disabled_config_falls_back_to_noop(self):
        from xcore.configurations.sections import TracingConfig
        from xcore.kernel.observability.tracing import Tracer

        tracer = Tracer("svc", TracingConfig(enabled=False, backend="opentelemetry"))
        with tracer.span("op") as span:
            pass
        # noop path: random uuid ids, no real correlation expected
        assert len(span.trace_id) == 32


class TestTraceContextPropagation:
    def test_inject_extract_round_trip(self):
        from xcore.kernel.observability.tracing import (
            extract_trace_context,
            inject_trace_context,
        )

        tracer = _make_otel_tracer("svc-a")

        carrier: dict[str, str] = {}
        with tracer.span("parent") as parent_span:
            inject_trace_context(carrier)

        assert "traceparent" in carrier

        ctx = extract_trace_context(carrier)
        with tracer.span("child", context=ctx) as child_span:
            pass

        assert child_span.trace_id == parent_span.trace_id

    def test_extract_empty_carrier_does_not_raise(self):
        from xcore.kernel.observability.tracing import extract_trace_context

        ctx = extract_trace_context({})
        assert ctx is not None


class TestWorkerTraceIdParsing:
    def test_none_carrier(self):
        from xcore.kernel.sandbox.worker import _trace_id_from_carrier

        assert _trace_id_from_carrier(None) is None

    def test_empty_carrier(self):
        from xcore.kernel.sandbox.worker import _trace_id_from_carrier

        assert _trace_id_from_carrier({}) is None

    def test_malformed_traceparent(self):
        from xcore.kernel.sandbox.worker import _trace_id_from_carrier

        assert _trace_id_from_carrier({"traceparent": "not-a-traceparent"}) is None

    def test_valid_traceparent(self):
        from xcore.kernel.sandbox.worker import _trace_id_from_carrier

        tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        assert (
            _trace_id_from_carrier({"traceparent": tp})
            == "4bf92f3577b34da6a3ce929d0e0e4736"
        )


class TestTraceContextMiddleware:
    def test_incoming_traceparent_becomes_span_parent(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from xcore.configurations.sections import TracingConfig
        from xcore.kernel.observability.http_middleware import TraceContextMiddleware
        from xcore.kernel.observability.tracing import Tracer

        app = FastAPI()
        app.add_middleware(TraceContextMiddleware)

        tracer = Tracer(
            "http-svc", TracingConfig(enabled=True, backend="opentelemetry")
        )
        captured: dict[str, str] = {}

        @app.get("/ping")
        async def ping():
            with tracer.span("handler") as span:
                captured["trace_id"] = span.trace_id
            return {"ok": True}

        client = TestClient(app)
        incoming_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        traceparent = f"00-{incoming_trace_id}-00f067aa0ba902b7-01"

        resp = client.get("/ping", headers={"traceparent": traceparent})

        assert resp.status_code == 200
        assert captured["trace_id"] == incoming_trace_id

    def test_no_traceparent_header_does_not_break_request(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from xcore.kernel.observability.http_middleware import TraceContextMiddleware

        app = FastAPI()
        app.add_middleware(TraceContextMiddleware)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


class TestTracerShutdown:
    """Placé en dernier : le TracerProvider OTel est un singleton par process
    (voir `_provider_configured`), donc shutdown() a un effet global — les
    autres tests de ce fichier ne dépendent que de trace_id/span_id/status,
    jamais du succès de l'export, donc l'ordre ne les affecte pas."""

    def test_noop_tracer_shutdown_is_safe(self):
        from xcore.kernel.observability.tracing import Tracer

        Tracer("svc").shutdown()  # pas de backend OTel configuré — ne doit pas lever

    def test_otel_tracer_shutdown_is_safe(self):
        tracer = _make_otel_tracer("svc-shutdown-test")
        with tracer.span("final"):
            pass
        tracer.shutdown()
        tracer.shutdown()  # idempotent
