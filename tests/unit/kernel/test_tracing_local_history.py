"""The local span history is bounded (issue #305, memory leak).

`TracingMiddleware` wraps every plugin call, so `Tracer.span()` is on the hot path even when tracing
is disabled. `Tracer._spans` was a plain list that nothing ever trimmed, so a `Span` leaked per call:
~562 B/call measured, about 4.9 GB/day per worker at 100 req/s.

What these tests defend:
- the history stops growing past its bound, whatever the number of calls;
- `export()` keeps working (it is the introspection/debug use case the history exists for) and shows
  the MOST RECENT spans, not the first ones;
- the bound is configurable, including `0` (keep nothing), and an absurd setting cannot turn the
  bound off — `deque(maxlen=None)` would be an unbounded list again, i.e. the leak.
"""

import pytest

from xcore.configurations.sections import TracingConfig
from xcore.kernel.observability.tracing import DEFAULT_MAX_LOCAL_SPANS, Tracer


def _run(tracer, count, name="op"):
    for i in range(count):
        with tracer.span(f"{name}-{i}"):
            pass


class TestLocalHistoryIsBounded:
    def test_history_stops_growing_past_the_bound(self):
        tracer = Tracer("svc", TracingConfig(max_local_spans=50))
        _run(tracer, 5_000)
        assert len(tracer._spans) == 50

    def test_default_bound_applies_without_any_configuration(self):
        tracer = Tracer("svc")
        _run(tracer, DEFAULT_MAX_LOCAL_SPANS * 2)
        assert len(tracer._spans) == DEFAULT_MAX_LOCAL_SPANS

    def test_export_keeps_working_and_shows_the_most_recent_spans(self):
        tracer = Tracer("svc", TracingConfig(max_local_spans=3))
        _run(tracer, 10)
        exported = tracer.export()
        assert [s["name"] for s in exported] == ["op-7", "op-8", "op-9"]
        assert all(
            s["duration_ms"] is not None and s["status"] == "ok" for s in exported
        )

    def test_zero_keeps_nothing_at_all(self):
        tracer = Tracer("svc", TracingConfig(max_local_spans=0))
        _run(tracer, 100)
        assert tracer.export() == []

    @pytest.mark.parametrize("value", [-1, None, "beaucoup", True, 2.5])
    def test_an_absurd_setting_never_removes_the_bound(self, value):
        """`deque(maxlen=None)` is an unbounded list — the leak itself. A bad setting must not reach it."""
        tracer = Tracer("svc", TracingConfig(max_local_spans=value))
        assert tracer._spans.maxlen is not None
        _run(tracer, DEFAULT_MAX_LOCAL_SPANS + 100)
        assert len(tracer._spans) <= DEFAULT_MAX_LOCAL_SPANS

    def test_a_span_still_carries_what_callers_read_from_it(self):
        """The bound must not change the span API: a caller sets attributes and reads ids/duration."""
        tracer = Tracer("svc", TracingConfig(max_local_spans=10))
        with tracer.span("op", tenant="acme") as span:
            span.set_attribute("rows", 3)
        assert span.attributes == {"tenant": "acme", "rows": 3}
        assert len(span.trace_id) == 32 and len(span.span_id) == 16
        assert span.duration_ms is not None
        assert tracer.export()[-1]["attributes"] == {"tenant": "acme", "rows": 3}
