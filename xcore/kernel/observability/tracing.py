"""
tracing.py — Interface de tracing.

Noop en mémoire par défaut (aucune configuration requise). Bascule vers un
TracerProvider OpenTelemetry réel quand `TracingConfig.enabled=True` et
`backend="opentelemetry"` : chaque span devient aussi un span OTel exporté
(console si pas d'`endpoint`, OTLP/HTTP sinon), avec trace_id/span_id réels
et propagation W3C TraceContext utilisable à travers process/HTTP.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generator, Mapping, MutableMapping

from opentelemetry import trace as otel_trace
from opentelemetry.propagate import extract as _otel_extract
from opentelemetry.propagate import inject as _otel_inject
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Status, StatusCode

from .logging import get_logger

if TYPE_CHECKING:
    from ...configurations.sections import TracingConfig

logger = get_logger("xcore.observability.tracing")

# Un seul TracerProvider global par process (recommandation OTel — les appels
# répétés à set_tracer_provider() au-delà du premier sont ignorés par le SDK).
_provider_configured = False


@dataclass
class Span:
    """
    Span de tracing.

    Enveloppe optionnellement un span OpenTelemetry réel (`_otel_span`) pour
    bénéficier de l'export SDK, sans changer l'API utilisée par les plugins
    et middlewares (`set_attribute`, `set_status`, `end`, `duration_ms`).
    """

    name: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    _otel_span: Any = field(default=None, repr=False, compare=False)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value
        if self._otel_span is not None:
            try:
                self._otel_span.set_attribute(key, value)
            except Exception:
                logger.debug("otel set_attribute failed", key=key)

    def set_status(self, status: str) -> None:
        self.status = status
        if self._otel_span is not None:
            self._otel_span.set_status(
                Status(StatusCode.ERROR if status == "error" else StatusCode.OK)
            )

    def end(self) -> None:
        self.end_time = time.monotonic()

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000


def _build_otel_tracer(service_name: str, config: "TracingConfig"):
    """Configure (une fois par process) le TracerProvider OTel et retourne un tracer nommé."""
    global _provider_configured
    if not _provider_configured:
        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        if endpoint := getattr(config, "endpoint", None):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=endpoint)
            exporter_name = "otlp"
            # Batché — évite un appel réseau par span vers le collecteur.
            provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            exporter = ConsoleSpanExporter()
            exporter_name = "console"
            # Synchrone — export immédiat, indispensable pour voir les spans
            # tout de suite en dev (BatchSpanProcessor attendrait jusqu'à 5s).
            provider.add_span_processor(SimpleSpanProcessor(exporter))
        otel_trace.set_tracer_provider(provider)
        _provider_configured = True
        logger.info(
            "opentelemetry tracer provider configured",
            service_name=service_name,
            exporter=exporter_name,
        )

    return otel_trace.get_tracer(service_name)


class Tracer:
    """
    Tracer facade.

    Sans configuration (ou `backend="noop"`), fonctionne en mémoire pure —
    aucun span n'est exporté, `.export()` renvoie juste l'historique local
    (utile en tests/dev). Avec `backend="opentelemetry"` et `enabled=True`,
    chaque `span()` est aussi un span OTel réel, corrélé via trace_id/span_id
    du SDK et exporté (console ou OTLP selon `endpoint`).
    """

    def __init__(
        self,
        service_name: str = "xcore",
        config: "TracingConfig | None" = None,
    ) -> None:
        self.service_name = service_name
        self._spans: list[Span] = []
        self._otel_tracer = None

        if (
            bool(getattr(config, "enabled", False))
            and getattr(config, "backend", "noop") == "opentelemetry"
        ):
            self._otel_tracer = _build_otel_tracer(service_name, config)

    def shutdown(self) -> None:
        """
        Flush et arrête le TracerProvider OTel (BatchSpanProcessor notamment)
        — à appeler explicitement à l'arrêt de l'app, sinon les spans encore
        dans le buffer batch au moment du shutdown sont perdus, jamais exportés.
        No-op si le backend n'est pas OpenTelemetry.
        """
        if self._otel_tracer is None:
            return
        try:
            otel_trace.get_tracer_provider().shutdown()
        except Exception:
            logger.debug("otel tracer provider shutdown failed", exc_info=True)

    @contextmanager
    def span(
        self, name: str, *, context: Any = None, **attrs
    ) -> Generator[Span, None, None]:
        """
        Crée un span et le retourne.

        `context` : contexte OTel parent explicite (ex. extrait d'un hop IPC
        ou d'un header HTTP via `extract_trace_context`). Sans lui, le span
        est enfant du contexte actif du process courant (comportement OTel
        standard — utile pour la corrélation intra-process automatique).
        """
        otel_span = None
        otel_cm = None
        if self._otel_tracer is not None:
            kwargs: dict[str, Any] = {}
            if context is not None:
                kwargs["context"] = context
            otel_cm = self._otel_tracer.start_as_current_span(name, **kwargs)
            otel_span = otel_cm.__enter__()
            for k, v in attrs.items():
                try:
                    otel_span.set_attribute(k, v)
                except Exception:
                    logger.debug("otel set_attribute failed", key=k)

        ctx = otel_span.get_span_context() if otel_span is not None else None
        s = Span(
            name=name,
            attributes=dict(attrs),
            trace_id=format(ctx.trace_id, "032x") if ctx else uuid.uuid4().hex,
            span_id=format(ctx.span_id, "016x") if ctx else uuid.uuid4().hex[:16],
        )
        s._otel_span = otel_span

        exc_info: tuple[Any, Any, Any] = (None, None, None)
        try:
            yield s
        except Exception as e:
            s.set_status("error")
            s.set_attribute("error.message", str(e))
            exc_info = (type(e), e, e.__traceback__)
            raise
        finally:
            s.end()
            self._spans.append(s)
            if otel_cm is not None:
                otel_cm.__exit__(*exc_info)

    def export(self) -> list[dict]:
        """Export local spans (introspection/debug — pas le pipeline d'export OTel)."""
        return [
            {
                "name": s.name,
                "trace_id": s.trace_id,
                "span_id": s.span_id,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "attributes": s.attributes,
            }
            for s in self._spans
        ]


def noop_tracer() -> Tracer:
    """Return a noop tracer."""
    return Tracer("noop")


def inject_trace_context(carrier: MutableMapping[str, str]) -> None:
    """Injecte le contexte de trace courant (W3C traceparent) dans `carrier`."""
    _otel_inject(carrier)


def extract_trace_context(carrier: Mapping[str, str]) -> Any:
    """Extrait un contexte de trace depuis `carrier` (headers HTTP, enveloppe IPC…)."""
    return _otel_extract(carrier)
