"""
health.py — Système de health checks pour xcore et ses services.
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class HealthStatus(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
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
    Registre de health checks.

    Usage:
        hc = HealthChecker()

        @hc.register("database")
        async def check_db():
            await db.execute("SELECT 1")
            return True, "OK"

        report = await hc.run_all()
    """

    def __init__(self) -> None:
        self._checks: dict[str, Callable] = {}

    def register(self, name: str) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._checks[name] = fn
            return fn
        return decorator

    async def run_all(self, timeout: float = 5.0) -> dict[str, Any]:
        results: list[CheckResult] = []
        for name, fn in self._checks.items():
            start = time.monotonic()
            try:
                if asyncio.iscoroutinefunction(fn):
                    ok, msg = await asyncio.wait_for(fn(), timeout=timeout)
                else:
                    ok, msg = fn()
                status = HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED
            except asyncio.TimeoutError:
                status, msg = HealthStatus.UNHEALTHY, f"Timeout après {timeout}s"
            except Exception as e:
                status, msg = HealthStatus.UNHEALTHY, str(e)

            duration = (time.monotonic() - start) * 1000
            results.append(CheckResult(name=name, status=status, message=msg, duration_ms=duration))

        overall = HealthStatus.HEALTHY
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            overall = HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            overall = HealthStatus.DEGRADED

        return {
            "status": overall.value,
            "checks": {r.name: {"status": r.status.value, "message": r.message,
                                "duration_ms": round(r.duration_ms, 2)} for r in results},
        }
