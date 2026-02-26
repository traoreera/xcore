"""
tracing.py — Interface de tracing (noop par défaut, OpenTelemetry optionnel).
"""
from __future__ import annotations
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class Span:
    name: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id:  str = field(default_factory=lambda: uuid.uuid4().hex[:16])
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
    """Tracer avec backend noop (extensible vers OpenTelemetry)."""

    def __init__(self, service_name: str = "xcore") -> None:
        self.service_name = service_name
        self._spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attrs) -> Generator[Span, None, None]:
        s = Span(name=name, attributes=attrs)
        try:
            yield s
        except Exception as e:
            s.set_status("error")
            s.set_attribute("error.message", str(e))
            raise
        finally:
            s.end()
            self._spans.append(s)

    def export(self) -> list[dict]:
        return [
            {"name": s.name, "trace_id": s.trace_id, "span_id": s.span_id,
             "duration_ms": s.duration_ms, "status": s.status,
             "attributes": s.attributes}
            for s in self._spans
        ]


def noop_tracer() -> Tracer:
    return Tracer("noop")
