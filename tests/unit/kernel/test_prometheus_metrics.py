"""Tests for Prometheus metrics wrappers."""

import pytest
from unittest.mock import MagicMock


class TestPrometheusWrappers:
    """Test _PrometheusCounter, _PrometheusGauge, _PrometheusHistogram directly."""

    def test_counter_inc_no_labels(self):
        from xcore.kernel.observability.metrics import _PrometheusCounter
        prom = MagicMock()
        prom._name = "test_counter"
        c = _PrometheusCounter(prom, {})
        c.inc(3.0)
        prom.inc.assert_called_once_with(3.0)

    def test_counter_inc_with_labels(self):
        from xcore.kernel.observability.metrics import _PrometheusCounter
        prom = MagicMock()
        prom._name = "test_counter"
        c = _PrometheusCounter(prom, {"plugin": "auth"})
        c.inc(2.0)
        prom.labels.assert_called_once_with(plugin="auth")
        prom.labels().inc.assert_called_once_with(2.0)

    def test_counter_value_always_zero(self):
        from xcore.kernel.observability.metrics import _PrometheusCounter
        prom = MagicMock()
        prom._name = "x"
        c = _PrometheusCounter(prom, {})
        assert c.value == 0.0

    def test_gauge_set_no_labels(self):
        from xcore.kernel.observability.metrics import _PrometheusGauge
        prom = MagicMock()
        prom._name = "test_gauge"
        g = _PrometheusGauge(prom, {})
        g.set(5.0)
        prom.set.assert_called_once_with(5.0)

    def test_gauge_inc_no_labels(self):
        from xcore.kernel.observability.metrics import _PrometheusGauge
        prom = MagicMock()
        prom._name = "test_gauge"
        g = _PrometheusGauge(prom, {})
        g.inc(1.0)
        prom.inc.assert_called_once_with(1.0)

    def test_gauge_dec_no_labels(self):
        from xcore.kernel.observability.metrics import _PrometheusGauge
        prom = MagicMock()
        prom._name = "test_gauge"
        g = _PrometheusGauge(prom, {})
        g.dec(1.0)
        prom.dec.assert_called_once_with(1.0)

    def test_gauge_with_labels(self):
        from xcore.kernel.observability.metrics import _PrometheusGauge
        prom = MagicMock()
        prom._name = "test_gauge"
        g = _PrometheusGauge(prom, {"env": "prod"})
        g.set(10.0)
        prom.labels.assert_called_once_with(env="prod")

    def test_gauge_value_always_zero(self):
        from xcore.kernel.observability.metrics import _PrometheusGauge
        prom = MagicMock()
        prom._name = "x"
        g = _PrometheusGauge(prom, {})
        assert g.value == 0.0

    def test_histogram_observe(self):
        from xcore.kernel.observability.metrics import _PrometheusHistogram
        prom = MagicMock()
        prom._name = "test_hist"
        h = _PrometheusHistogram(prom)
        h.observe(0.1)
        prom.observe.assert_called_once_with(0.1)

    def test_histogram_count_zero(self):
        from xcore.kernel.observability.metrics import _PrometheusHistogram
        prom = MagicMock()
        prom._name = "x"
        h = _PrometheusHistogram(prom)
        assert h.count == 0
        assert h.sum == 0.0
        assert h.mean == 0.0

    def test_histogram_name(self):
        from xcore.kernel.observability.metrics import _PrometheusHistogram
        prom = MagicMock()
        prom._name = "my_hist"
        h = _PrometheusHistogram(prom)
        assert h.name == "my_hist"


class TestPrometheusRegistry:
    """Test PrometheusMetricsRegistry with real prometheus_client."""

    def test_create_registry(self):
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            assert reg is not None
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_counter(self):
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            c = reg.counter("test_prom_counter_x1")
            assert c is not None
            c.inc()
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_counter_with_labels(self):
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            c = reg.counter("test_prom_labeled_x2", labels={"plugin": "auth"})
            assert c is not None
            c.inc(2.0)
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_gauge(self):
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            g = reg.gauge("test_prom_gauge_x3")
            assert g is not None
            g.set(5.0)
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_histogram(self):
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            h = reg.histogram("test_prom_hist_x4")
            assert h is not None
            h.observe(0.1)
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_snapshot(self):
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            snap = reg.snapshot()
            assert "backend" in snap
            assert snap["backend"] == "prometheus"
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_counter_reuse(self):
        """Counter with same name should be reused without ValueError."""
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            c1 = reg.counter("test_prom_reuse_x5")
            c2 = reg.counter("test_prom_reuse_x5")
            assert c1 is c2
        except ImportError:
            pytest.skip("prometheus_client not installed")
