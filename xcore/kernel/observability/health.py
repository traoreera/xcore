"""
health.py — Système de health checks avec distinction liveness / readiness.

- liveness  : "le processus est-il vivant ?" — jamais de dépendances externes
- readiness : "peut-il recevoir du trafic ?" — inclut DB, cache, etc.

Endpoints exposés par le router :
  GET /health        → résumé global (liveness + readiness)
  GET /health/live   → liveness seul  (pour k8s livenessProbe)
  GET /health/ready  → readiness seul (pour k8s readinessProbe)
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal

HealthKind = Literal["liveness", "readiness"]


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class CheckResult:
    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """
    Registre de health checks avec distinction liveness / readiness.

    Usage:
    ```python
        hc = HealthChecker()

        @hc.register("process", kind="liveness")
        async def check_loop():
            return True, "event loop ok"

        @hc.register("database", kind="readiness")
        async def check_db():
            await db.execute("SELECT 1")
            return True, "ok"

        # k8s liveness probe
        live = await hc.run_liveness()

        # k8s readiness probe
        ready = await hc.run_readiness()

        # résumé complet
        report = await hc.run_all()
    ```
    """

    def __init__(self) -> None:
        # (fn, is_async, kind)
        self._checks: dict[str, tuple[Callable, bool, HealthKind]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register basic liveness checks."""

        @self.register("process", kind="liveness")
        def check_process():
            return True, "running"

        @self.register("event_loop", kind="liveness")
        async def check_loop():
            # If this runs, the loop is not blocked
            return True, "responsive"

    def register(self, name: str, kind: HealthKind = "readiness") -> Callable:
        """
        Decorator to register a health check.

        Args:
            name: identifier for this check
            kind: "liveness" (process alive) or "readiness" (ready for traffic)
        """

        def decorator(fn: Callable) -> Callable:
            self._checks[name] = (fn, inspect.iscoroutinefunction(fn), kind)
            return fn

        return decorator

    async def _run(
        self, kind: HealthKind | None, timeout: float = 5.0
    ) -> dict[str, Any]:
        checks = {
            name: (fn, is_async)
            for name, (fn, is_async, k) in self._checks.items()
            if kind is None or k == kind
        }

        results: list[CheckResult] = []
        for name, (fn, is_async) in checks.items():
            start = time.monotonic()
            try:
                ok, msg = (
                    await asyncio.wait_for(fn(), timeout=timeout) if is_async else fn()
                )
                status = HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED
            except asyncio.TimeoutError:
                status, msg = HealthStatus.UNHEALTHY, f"timeout après {timeout}s"
            except Exception as e:
                status, msg = HealthStatus.UNHEALTHY, str(e)

            duration = (time.monotonic() - start) * 1000
            results.append(
                CheckResult(name=name, status=status, message=msg, duration_ms=duration)
            )

        overall = HealthStatus.HEALTHY
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            overall = HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            overall = HealthStatus.DEGRADED

        return {
            "status": overall.value,
            "checks": {
                r.name: {
                    "status": r.status.value,
                    "message": r.message,
                    "duration_ms": round(r.duration_ms, 2),
                }
                for r in results
            },
        }

    async def run_all(self, timeout: float = 5.0) -> dict[str, Any]:
        """Run all checks (liveness + readiness)."""
        return await self._run(kind=None, timeout=timeout)

    async def run_liveness(self, timeout: float = 5.0) -> dict[str, Any]:
        """Run liveness checks only — for k8s livenessProbe."""
        return await self._run(kind="liveness", timeout=timeout)

    async def run_readiness(self, timeout: float = 5.0) -> dict[str, Any]:
        """Run readiness checks only — for k8s readinessProbe."""
        return await self._run(kind="readiness", timeout=timeout)
