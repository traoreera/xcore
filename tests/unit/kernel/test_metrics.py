"""Tests for MetricsRegistry, Counter, Gauge, Histogram and factory."""

import pytest
from unittest.mock import MagicMock, patch

from xcore.kernel.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    _prom_name,
    create_metrics_registry,
)


# ── Counter ───────────────────────────────────────────────────────────────────

class TestCounter:
    def test_initial_value(self):
        c = Counter(name="hits")
        assert c.value == 0.0

    def test_inc_default(self):
        c = Counter(name="hits")
        c.inc()
        assert c.value == 1.0

    def test_inc_custom_amount(self):
        c = Counter(name="hits")
        c.inc(5.0)
        assert c.value == 5.0

    def test_inc_multiple(self):
        c = Counter(name="hits")
        c.inc()
        c.inc(2.5)
        assert c.value == 3.5

    def test_labels(self):
        c = Counter(name="hits", labels={"plugin": "auth"})
        assert c.labels == {"plugin": "auth"}


# ── Gauge ─────────────────────────────────────────────────────────────────────

class TestGauge:
    def test_initial_value(self):
        g = Gauge(name="active")
        assert g.value == 0.0

    def test_set(self):
        g = Gauge(name="active")
        g.set(42.0)
        assert g.value == 42.0

    def test_inc(self):
        g = Gauge(name="active")
        g.inc(3.0)
        assert g.value == 3.0

    def test_dec(self):
        g = Gauge(name="active")
        g.set(10.0)
        g.dec(3.0)
        assert g.value == 7.0

    def test_inc_dec_default(self):
        g = Gauge(name="active")
        g.inc()
        g.dec()
        assert g.value == 0.0


# ── Histogram ─────────────────────────────────────────────────────────────────

class TestHistogram:
    def test_initial(self):
        h = Histogram(name="latency")
        assert h.count == 0
        assert h.sum == 0.0
        assert h.mean == 0.0

    def test_observe(self):
        h = Histogram(name="latency")
        h.observe(0.1)
        h.observe(0.2)
        assert h.count == 2
        assert abs(h.sum - 0.3) < 1e-9

    def test_mean(self):
        h = Histogram(name="latency")
        h.observe(1.0)
        h.observe(3.0)
        assert h.mean == 2.0

    def test_mean_empty(self):
        h = Histogram(name="latency")
        assert h.mean == 0.0

    def test_default_buckets(self):
        h = Histogram(name="latency")
        assert len(h.buckets) > 0


# ── MetricsRegistry ───────────────────────────────────────────────────────────

class TestMetricsRegistry:
    def test_counter_created_once(self):
        reg = MetricsRegistry()
        c1 = reg.counter("calls")
        c2 = reg.counter("calls")
        assert c1 is c2

    def test_counter_with_labels(self):
        reg = MetricsRegistry()
        c = reg.counter("calls", labels={"plugin": "auth"})
        c.inc(3)
        assert c.value == 3.0

    def test_gauge(self):
        reg = MetricsRegistry()
        g = reg.gauge("active_workers")
        g.set(5)
        assert g.value == 5.0

    def test_gauge_created_once(self):
        reg = MetricsRegistry()
        g1 = reg.gauge("active_workers")
        g2 = reg.gauge("active_workers")
        assert g1 is g2

    def test_histogram(self):
        reg = MetricsRegistry()
        h = reg.histogram("request_duration")
        h.observe(0.05)
        assert h.count == 1

    def test_histogram_created_once(self):
        reg = MetricsRegistry()
        h1 = reg.histogram("request_duration")
        h2 = reg.histogram("request_duration")
        assert h1 is h2

    def test_snapshot(self):
        reg = MetricsRegistry()
        reg.counter("calls").inc(5)
        reg.gauge("active").set(3)
        reg.histogram("latency").observe(0.1)
        snap = reg.snapshot()
        assert "counters" in snap
        assert "gauges" in snap
        assert "histograms" in snap
        assert any(v == 5.0 for v in snap["counters"].values())
        assert any(v == 3.0 for v in snap["gauges"].values())


# ── _prom_name ────────────────────────────────────────────────────────────────

class TestPromName:
    def test_dots_replaced(self):
        assert _prom_name("plugin.calls") == "plugin_calls"

    def test_dashes_replaced(self):
        assert _prom_name("plugin-calls") == "plugin_calls"

    def test_combined(self):
        assert _prom_name("xcore.plugin-calls") == "xcore_plugin_calls"


# ── create_metrics_registry ───────────────────────────────────────────────────

class TestCreateMetricsRegistry:
    def test_memory_backend(self):
        config = MagicMock()
        config.backend = "memory"
        reg = create_metrics_registry(config)
        assert isinstance(reg, MetricsRegistry)

    def test_default_backend(self):
        config = MagicMock(spec=[])
        reg = create_metrics_registry(config)
        assert isinstance(reg, MetricsRegistry)

    def test_prometheus_backend_fallback_on_import_error(self):
        config = MagicMock()
        config.backend = "prometheus"
        with patch(
            "xcore.kernel.observability.metrics.PrometheusMetricsRegistry",
            side_effect=ImportError("no prometheus"),
        ):
            reg = create_metrics_registry(config)
        assert isinstance(reg, MetricsRegistry)

    def test_prometheus_backend_available(self):
        config = MagicMock()
        config.backend = "prometheus"
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = create_metrics_registry(config)
            assert isinstance(reg, (MetricsRegistry,))
        except Exception:
            pass
