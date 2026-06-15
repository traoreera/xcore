"""
— Lightweight metrics registry (default memory backend).
Prometheus-compatible interface if the backend is configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import MetricsConfig


@dataclass
class Counter:
    """A counter metric."""

    name: str
    labels: dict[str, str] = field(default_factory=dict)
    _value: float = 0.0

    def inc(self, amount: float = 1.0) -> None:
        self._value += amount

    @property
    def value(self) -> float:
        return self._value


@dataclass
class Gauge:
    name: str
    labels: dict[str, str] = field(default_factory=dict)
    _value: float = 0.0

    def set(self, v: float) -> None:
        self._value = v

    def inc(self, v: float = 1.0) -> None:
        self._value += v

    def dec(self, v: float = 1.0) -> None:
        self._value -= v

    @property
    def value(self) -> float:
        return self._value


@dataclass
class Histogram:
    name: str
    buckets: list[float] = field(
        default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.5, 1, 5, 10]
    )
    _observations: list[float] = field(default_factory=list)

    def observe(self, v: float) -> None:
        self._observations.append(v)

    @property
    def count(self) -> int:
        return len(self._observations)

    @property
    def sum(self) -> float:
        return sum(self._observations)

    @property
    def mean(self) -> float:
        return self.sum / self.count if self.count else 0.0


class MetricsRegistry:
    """
        A simple in-memory metrics registry.

        Usage:
    ```python
            registry = MetricsRegistry()
            calls = registry.counter("plugin.calls", labels={"plugin": "my_plugin"})
            calls.inc()

            latency = registry.histogram("plugin.latency_seconds")
            latency.observe(0.042)```
    """

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

    def counter(self, name: str, labels: dict | None = None) -> Counter:
        key = f"{name}:{labels}"
        if key not in self._counters:
            self._counters[key] = Counter(name=name, labels=labels or {})
        return self._counters[key]

    def gauge(self, name: str, labels: dict | None = None) -> Gauge:
        """Return a gauge metric."""
        key = f"{name}:{labels}"
        if key not in self._gauges:
            self._gauges[key] = Gauge(name=name, labels=labels or {})
        return self._gauges[key]

    def histogram(self, name: str) -> Histogram:
        """Return a histogram metric."""
        if name not in self._histograms:
            self._histograms[name] = Histogram(name=name)
        return self._histograms[name]

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the metrics registry."""
        return {
            "counters": {k: v.value for k, v in self._counters.items()},
            "gauges": {k: v.value for k, v in self._gauges.items()},
            "histograms": {
                k: {"count": v.count, "sum": v.sum, "mean": v.mean}
                for k, v in self._histograms.items()
            },
        }


# ── Prometheus wrappers ───────────────────────────────────────────────────────


class _PrometheusCounter:
    """Wrapper autour de prometheus_client.Counter."""

    def __init__(self, prom_counter, label_values: dict) -> None:
        self._prom = prom_counter
        self._label_values = label_values
        self.name = prom_counter._name

    def inc(self, amount: float = 1.0) -> None:
        if self._label_values:
            self._prom.labels(**self._label_values).inc(amount)
        else:
            self._prom.inc(amount)

    @property
    def value(self) -> float:
        # Prometheus ne expose pas la valeur en Python — retourne 0
        return 0.0


class _PrometheusGauge:
    """Wrapper autour de prometheus_client.Gauge."""

    def __init__(self, prom_gauge, label_values: dict) -> None:
        self._prom = prom_gauge
        self._label_values = label_values
        self.name = prom_gauge._name

    def _labeled(self):
        if self._label_values:
            return self._prom.labels(**self._label_values)
        return self._prom

    def set(self, v: float, labels=None) -> None:
        self._labeled().set(v)

    def inc(self, v: float = 1.0) -> None:
        self._labeled().inc(v)

    def dec(self, v: float = 1.0) -> None:
        self._labeled().dec(v)

    @property
    def value(self) -> float:
        return 0.0


class _PrometheusHistogram:
    """Wrapper autour de prometheus_client.Histogram."""

    def __init__(self, prom_histogram) -> None:
        self._prom = prom_histogram
        self.name = prom_histogram._name

    def observe(self, v: float) -> None:
        self._prom.observe(v)

    @property
    def count(self) -> int:
        return 0

    @property
    def sum(self) -> float:
        return 0.0

    @property
    def mean(self) -> float:
        return 0.0


def _prom_name(name: str) -> str:
    """Convertit un nom xcore (avec points) en nom Prometheus (avec underscores)."""
    return name.replace(".", "_").replace("-", "_")


def _get_or_create_prom_metric(
    metric_class, prom_name: str, label_names: list[str], **kwargs
):
    """Crée ou récupère un metric Prometheus existant (évite ValueError sur double enregistrement)."""
    import prometheus_client

    try:
        return metric_class(prom_name, prom_name, label_names, **kwargs)
    except ValueError:
        # Metric déjà enregistré — récupère depuis le registry
        collectors = prometheus_client.REGISTRY._names_to_collectors
        # Cherche par nom exact ou avec suffixe _total
        for key in (prom_name, prom_name + "_total"):
            if key in collectors:
                return collectors[key]
        # Fallback : cherche en itérant
        for col in prometheus_client.REGISTRY._collectors:
            if hasattr(col, "_name") and col._name == prom_name:
                return col
        raise


class PrometheusMetricsRegistry:
    """
    MetricsRegistry utilisant prometheus_client comme backend.

    Si prometheus_client n'est pas installé, instancier cette classe lèvera ImportError.
    Utiliser create_metrics_registry() pour un fallback automatique.
    """

    def __init__(self) -> None:
        import prometheus_client  # noqa: F401 — vérifie la disponibilité

        self._counters: dict[str, _PrometheusCounter] = {}
        self._gauges: dict[str, _PrometheusGauge] = {}
        self._histograms: dict[str, _PrometheusHistogram] = {}

    def counter(self, name: str, labels: dict | None = None) -> _PrometheusCounter:
        import prometheus_client

        pname = _prom_name(name)
        if not pname.endswith("_total"):
            pname = pname + "_total"
        label_names = sorted(labels.keys()) if labels else []
        key = f"{name}:{labels}"
        if key not in self._counters:
            prom_counter = _get_or_create_prom_metric(
                prometheus_client.Counter, pname, label_names
            )
            self._counters[key] = _PrometheusCounter(prom_counter, labels or {})
        return self._counters[key]

    def gauge(self, name: str, labels: dict | None = None) -> _PrometheusGauge:
        import prometheus_client

        pname = _prom_name(name)
        label_names = sorted(labels.keys()) if labels else []
        key = f"{name}:{labels}"
        if key not in self._gauges:
            prom_gauge = _get_or_create_prom_metric(
                prometheus_client.Gauge, pname, label_names
            )
            self._gauges[key] = _PrometheusGauge(prom_gauge, labels or {})
        return self._gauges[key]

    def histogram(self, name: str) -> _PrometheusHistogram:
        import prometheus_client

        pname = _prom_name(name)
        if name not in self._histograms:
            prom_hist = _get_or_create_prom_metric(
                prometheus_client.Histogram, pname, []
            )
            self._histograms[name] = _PrometheusHistogram(prom_hist)
        return self._histograms[name]

    def snapshot(self) -> dict[str, Any]:
        return {"backend": "prometheus", "note": "use /metrics endpoint"}


# ── Factory ───────────────────────────────────────────────────────────────────


def create_metrics_registry(config: "MetricsConfig") -> MetricsRegistry:
    """
    Factory qui crée le bon MetricsRegistry selon la config.

    - backend="prometheus" → PrometheusMetricsRegistry (fallback memory si absent)
    - sinon → MetricsRegistry (in-memory)
    """
    if getattr(config, "backend", "memory") == "prometheus":
        try:
            return PrometheusMetricsRegistry()
        except ImportError:
            return MetricsRegistry()
    return MetricsRegistry()
