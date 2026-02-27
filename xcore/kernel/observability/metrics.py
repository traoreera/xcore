"""
metrics.py — Registre de métriques léger (memory backend par défaut).
Interface compatible Prometheus si le backend est configuré.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Counter:
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
    Registre central des métriques.

    Usage:
        registry = MetricsRegistry()
        calls = registry.counter("plugin.calls", labels={"plugin": "my_plugin"})
        calls.inc()

        latency = registry.histogram("plugin.latency_seconds")
        latency.observe(0.042)
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
        key = f"{name}:{labels}"
        if key not in self._gauges:
            self._gauges[key] = Gauge(name=name, labels=labels or {})
        return self._gauges[key]

    def histogram(self, name: str) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name=name)
        return self._histograms[name]

    def snapshot(self) -> dict[str, Any]:
        return {
            "counters": {k: v.value for k, v in self._counters.items()},
            "gauges": {k: v.value for k, v in self._gauges.items()},
            "histograms": {
                k: {"count": v.count, "sum": v.sum, "mean": v.mean}
                for k, v in self._histograms.items()
            },
        }
