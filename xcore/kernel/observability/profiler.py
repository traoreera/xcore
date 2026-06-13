"""
profiler.py — Profilage mémoire/CPU par plugin via psutil.

Deux sources :
- Plugins trusted   : processus principal partagé — on mesure la delta RSS
  en enregistrant l'usage avant/après on_load puis en lisant la tendance.
- Plugins sandboxed : subprocess isolé — on lit directement le PID via psutil.

Les métriques sont publiées :
1. Dans le MetricsRegistry (Gauges Prometheus) — visibles dans /metrics
2. Via PluginProfiler.snapshot() — consommé par l'endpoint /plugins/metrics
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .metrics import MetricsRegistry

try:
    import psutil

    _PSUTIL = True
except ImportError:
    _PSUTIL = False

from . import get_logger

logger = get_logger("xcore.observability.profiler")


@dataclass
class PluginSample:
    plugin: str
    pid: int | None  # None = trusted (in-process)
    rss_mb: float
    cpu_percent: float
    sampled_at: float = field(default_factory=time.monotonic)


class PluginProfiler:
    """
    Collecte périodiquement RSS + CPU pour chaque plugin enregistré.

    Usage (kernel) :
    ```python
        profiler = PluginProfiler(metrics=self.metrics)

        # Plugin trusted — pid=None, on lit le process courant
        profiler.register("shop", pid=None)

        # Plugin sandboxed — pid du subprocess
        profiler.register("billing", pid=12345)

        await profiler.start(interval_seconds=15)
        ...
        await profiler.stop()

        snapshot = profiler.snapshot()  # dict plugin → dernière mesure
    ```
    """

    def __init__(self, metrics: "MetricsRegistry | None" = None) -> None:
        self._metrics = metrics
        # plugin_name → pid (None = in-process)
        self._plugins: dict[str, int | None] = {}
        # plugin_name → dernière mesure
        self._last: dict[str, PluginSample] = {}
        self._task: asyncio.Task | None = None

        if not _PSUTIL:
            logger.warning(
                "psutil absent — profilage par plugin désactivé",
                hint="pip install psutil",
            )

        if metrics:
            self._g_rss = metrics.gauge("plugin_memory_rss_mb")
            self._g_cpu = metrics.gauge("plugin_cpu_percent")
        else:
            self._g_rss = None
            self._g_cpu = None

    def register(self, plugin_name: str, pid: int | None) -> None:
        """Register a plugin for profiling. pid=None for in-process trusted plugins."""
        self._plugins[plugin_name] = pid

    def unregister(self, plugin_name: str) -> None:
        self._plugins.pop(plugin_name, None)
        self._last.pop(plugin_name, None)

    def update_pid(self, plugin_name: str, pid: int | None) -> None:
        """Update the PID for a sandboxed plugin after a restart."""
        if plugin_name in self._plugins:
            self._plugins[plugin_name] = pid

    async def start(self, interval_seconds: float = 15.0) -> None:
        if not _PSUTIL:
            return
        self._task = asyncio.create_task(
            self._loop(interval_seconds), name="xcore.profiler"
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return the last sample for each registered plugin."""
        return {
            name: {
                "pid": s.pid,
                "rss_mb": round(s.rss_mb, 2),
                "cpu_percent": round(s.cpu_percent, 2),
                "sampled_at": s.sampled_at,
            }
            for name, s in self._last.items()
        }

    async def _loop(self, interval: float) -> None:
        # psutil CPU % needs a first call to initialize the counter
        self._collect(first_call=True)
        while True:
            await asyncio.sleep(interval)
            self._collect()

    def _collect(self, first_call: bool = False) -> None:
        main_proc = psutil.Process()

        for plugin_name, pid in list(self._plugins.items()):
            try:
                if pid is None:
                    # Trusted plugin — measure the main process
                    proc = main_proc
                else:
                    proc = psutil.Process(pid)

                rss_mb = proc.memory_info().rss / 1_048_576
                # interval=None → % since last call to cpu_percent on this proc
                cpu = proc.cpu_percent(interval=None)

                if first_call:
                    # First call always returns 0.0 for cpu_percent; skip publishing
                    continue

                sample = PluginSample(
                    plugin=plugin_name, pid=pid, rss_mb=rss_mb, cpu_percent=cpu
                )
                self._last[plugin_name] = sample

                labels = {"plugin": plugin_name}
                if self._g_rss:
                    self._g_rss.set(rss_mb, labels=labels)
                if self._g_cpu:
                    self._g_cpu.set(cpu, labels=labels)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.warning(
                    "profiler: process not found", plugin=plugin_name, pid=pid
                )
                self._last.pop(plugin_name, None)
            except Exception as e:
                logger.error("profiler error", plugin=plugin_name, error=str(e))
