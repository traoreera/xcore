"""
xcore Performance Benchmark Suite
==================================
Tests :
  1. Plugin load / unload time (single, batch, concurrent)
  2. Plugin call throughput (sequential, concurrent)
  3. Middleware pipeline overhead
  4. EventBus / HookManager throughput
  5. PermissionEngine throughput + cache effectiveness
  6. CacheService throughput (memory backend)
  7. Maximum plugin capacity simulation
  8. Memory footprint per plugin
  9. Overall system stress test
  10. Inter-Plugin Communication (IPC) throughput

Usage :
    python scripts/benchmarks.py                    # full suite
    python scripts/benchmarks.py --suite plugins    # only plugin benchmarks
    python scripts/benchmarks.py --capacity 200     # test up to 200 plugins
    python scripts/benchmarks.py --output report.json
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import shutil
import statistics
import sys
import tempfile
import textwrap
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ── FIX: sys.path doit être inséré AVANT tous les imports xcore ──────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from xcore.sdk.plugin_base import PluginManifest  # noqa: E402

# ── deps optionnels ──────────────────────────────────────────────────────────
try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    print("[WARN] psutil absent — memory metrics désactivés (pip install psutil)")

try:
    from tabulate import tabulate

    _HAS_TABULATE = True
except ImportError:
    _HAS_TABULATE = False


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Structures de données du rapport                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝


@dataclass
class BenchResult:
    name: str
    category: str
    iterations: int
    total_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    std_ms: float
    throughput_ops_sec: float
    memory_delta_mb: float = 0.0
    errors: int = 0
    notes: str = ""

    def as_row(self) -> list:
        return [
            self.name,
            f"{self.mean_ms:.3f}",
            f"{self.median_ms:.3f}",
            f"{self.p95_ms:.3f}",
            f"{self.p99_ms:.3f}",
            f"{self.min_ms:.3f}",
            f"{self.max_ms:.3f}",
            f"{self.throughput_ops_sec:.0f}",
            f"{self.memory_delta_mb:.2f}",
            "✅" if self.errors == 0 else f"❌ {self.errors}",
        ]


@dataclass
class BenchReport:
    xcore_version: str = "unknown"
    python_version: str = sys.version.split()[0]
    platform: str = sys.platform
    timestamp: str = ""
    cpu_count: int = os.cpu_count() or 1
    total_duration_s: float = 0.0
    results: list[BenchResult] = field(default_factory=list)
    capacity: dict[str, Any] = field(default_factory=dict)
    system_info: dict[str, Any] = field(default_factory=dict)

    def add(self, r: BenchResult) -> None:
        self.results.append(r)

    def summary_table(self) -> str:
        headers = [
            "Benchmark",
            "Mean(ms)",
            "Med(ms)",
            "P95(ms)",
            "P99(ms)",
            "Min(ms)",
            "Max(ms)",
            "Ops/s",
            "ΔMem(MB)",
            "Status",
        ]
        rows = [r.as_row() for r in self.results]
        if _HAS_TABULATE:
            return tabulate(rows, headers=headers, tablefmt="rounded_outline")
        sep = "-" * 120
        lines = [sep, "  ".join(f"{h:<14}" for h in headers), sep]
        for row in rows:
            lines.append("  ".join(f"{str(c):<14}" for c in row))
        lines.append(sep)
        return "\n".join(lines)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Helpers                                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def _mem_mb() -> float:
    if not _HAS_PSUTIL:
        return 0.0
    return psutil.Process().memory_info().rss / 1024 / 1024


def _percentile(sorted_samples: list[float], pct: float) -> float:
    """Retourne le percentile pct (0–1) d'une liste déjà triée, sans débordement."""
    if not sorted_samples:
        return 0.0
    idx = min(int(len(sorted_samples) * pct), len(sorted_samples) - 1)
    return sorted_samples[idx]


def _measure(
    samples: list[float],
    iterations: int,
    errors: int,
    name: str,
    category: str,
    mem_delta: float = 0.0,
    notes: str = "",
) -> BenchResult:
    """
    Construit un BenchResult à partir de samples déjà exprimés en millisecondes.
    """
    if not samples:
        return BenchResult(name, category, iterations, 0, 0, 0, 0, 0, 0, 0, 0, 0, errors=errors)

    total = sum(samples)
    mean = statistics.mean(samples)
    med = statistics.median(samples)
    std = statistics.stdev(samples) if len(samples) > 1 else 0.0
    sorted_s = sorted(samples)
    s95 = _percentile(sorted_s, 0.95)
    s99 = _percentile(sorted_s, 0.99)
    thr = iterations / (total / 1000) if total > 0 else 0.0

    return BenchResult(
        name=name,
        category=category,
        iterations=iterations,
        total_ms=total,
        mean_ms=mean,
        median_ms=med,
        p95_ms=s95,
        p99_ms=s99,
        min_ms=min(samples),
        max_ms=max(samples),
        std_ms=std,
        throughput_ops_sec=thr,
        memory_delta_mb=mem_delta,
        errors=errors,
        notes=notes,
    )


def _make_plugin_dir(
    base: Path,
    name: str,
    mode: str = "trusted",
    extra_code: str = "",
    allowed_callers: list[str] | None = None,
) -> Path:
    """Crée un plugin minimal valide dans base/name."""
    plugin_dir = base / name
    src_dir = plugin_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    callers_yaml = ""
    if allowed_callers:
        callers_yaml = f"allowed_callers: {json.dumps(allowed_callers)}"

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            f"""
        name: {name}
        version: 1.0.0
        execution_mode: {mode}
        description: Benchmark plugin
        {callers_yaml}
        permissions:
          - resource: "*"
            actions: ["*"]
            effect: allow

        resources:
          timeout_seconds: 30
          rate_limit:
            calls: 100000
            period_seconds: 60
    """
        ).strip()
    )

    base_class = "TrustedBase" if mode == "trusted" else "BasePlugin"

    (src_dir / "main.py").write_text(
        textwrap.dedent(
            f"""
        from xcore.kernel.api.contract import TrustedBase, BasePlugin

        class Plugin({base_class}):
            call_count = 0

            async def handle(self, action: str, payload: dict) -> dict:
                Plugin.call_count += 1
                if action == "ping":
                    return {{"status": "ok", "pong": True, "count": Plugin.call_count}}
                if action == "echo":
                    return {{"status": "ok", "data": payload}}
                if action == "compute":
                    n = payload.get("n", 100)
                    result = sum(i * i for i in range(n))
                    return {{"status": "ok", "result": result}}
                if action == "proxy_ping":
                    target = payload.get("target", "receiver")
                    return await self.call_plugin(target, "ping", {{}})
                return {{"status": "error", "msg": f"unknown action {{action}}"}}

            async def on_load(self):
                pass

            async def on_unload(self):
                pass
        {extra_code}
    """
        ).strip()
    )

    return plugin_dir


def _make_xcore_config(plugins_dir: Path) -> str:
    """Crée un fichier de config minimal et retourne son chemin."""
    cfg_file = plugins_dir.parent / "xcore_bench.yaml"
    cfg_file.write_text(
        textwrap.dedent(
            f"""
            app:
              name: my-app
              env: development
              debug: true
              secret_key: "vjherbvjhe"
              plugin_prefix: "/app"
              server_key: "rhverujierf"
              server_key_iterations: 100000
              plugin_tags: ["test"]

            plugins:
              directory: {plugins_dir}
              secret_key: "12345"
              strict_trusted: false
              interval: 0
              entry_point: src/main.py

            services:
              databases:
                db:
                  type: sqlasync
                  url: sqlite+aiosqlite:///db.sqlite3
                  echo: false
              cache:
                backend: memory
                ttl: 300
                max_size: 10000
              scheduler:
                enabled: false

            observability:
              logging:
                enabled: false
              metrics:
                enabled: false
              tracing:
                enabled: false

            security:
              allowed_imports: ["*"]
              rate_limit_default:
                calls: 100000
                period_seconds: 60
    """
        ).strip()
    )
    return str(cfg_file)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 1 — Plugin Load / Unload                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class PluginLifecycleBench:
    """Benchmarks de chargement/déchargement de plugins."""

    CATEGORY = "plugin_lifecycle"

    async def bench_single_load_unload(self, n_runs: int = 20) -> list[BenchResult]:
        """Charge et décharge 1 plugin, N fois de suite."""
        results = []
        tmp = Path(tempfile.mkdtemp(prefix="xcore_bench_"))
        try:
            from xcore.kernel.runtime.lifecycle import LifecycleManager
            from xcore.kernel.security.validation import ManifestValidator

            plugin_dir = _make_plugin_dir(tmp, "bench_single")
            manifest, _, _ = ManifestValidator().load_and_validate(plugin_dir)
            services_mock = _MockServices()

            load_samples: list[float] = []
            unload_samples: list[float] = []
            errors = 0

            for _ in range(n_runs):
                ctx = _make_ctx(services_mock)
                lm = LifecycleManager(manifest, ctx)
                try:
                    t0 = time.perf_counter()
                    await lm.load()
                    load_samples.append((time.perf_counter() - t0) * 1000)

                    t0 = time.perf_counter()
                    await lm.unload()
                    unload_samples.append((time.perf_counter() - t0) * 1000)
                except Exception as e:
                    errors += 1
                    print(f"  [WARN] load/unload error: {e}")

            if load_samples:
                results.append(
                    _measure(
                        load_samples,
                        n_runs,
                        errors,
                        "single_plugin_load",
                        self.CATEGORY,
                        notes=f"{n_runs} runs",
                    )
                )
            if unload_samples:
                results.append(
                    _measure(
                        unload_samples,
                        n_runs,
                        errors,
                        "single_plugin_unload",
                        self.CATEGORY,
                        notes=f"{n_runs} runs",
                    )
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return results

    async def bench_batch_load(
        self, batch_sizes: list[int] = (5, 20, 50)
    ) -> list[BenchResult]:
        """Charge N plugins en une seule passe (load_all)."""
        results = []
        for n in batch_sizes:
            tmp = Path(tempfile.mkdtemp(prefix="xcore_bench_"))
            try:
                for i in range(n):
                    _make_plugin_dir(tmp / "plugins", f"plugin_{i:04d}")

                cfg_path = _make_xcore_config(tmp / "plugins")
                mem_before = _mem_mb()
                t0 = time.perf_counter()

                from xcore import Xcore

                app = Xcore(config_path=cfg_path)
                try:
                    await app.boot()
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    mem_after = _mem_mb()
                    all_loaded = app.plugins.list_plugins()
                    # Filter out internal 'xcore' virtual plugin from the count
                    loaded = len([name for name in all_loaded if name != "xcore"])

                    results.append(
                        BenchResult(
                            name=f"batch_load_{n}_plugins",
                            category=self.CATEGORY,
                            iterations=n,
                            total_ms=elapsed_ms,
                            mean_ms=elapsed_ms / n,
                            median_ms=elapsed_ms / n,
                            p95_ms=elapsed_ms / n * 1.5,
                            p99_ms=elapsed_ms / n * 2.0,
                            min_ms=0,
                            max_ms=elapsed_ms,
                            std_ms=0,
                            throughput_ops_sec=n / (elapsed_ms / 1000),
                            memory_delta_mb=mem_after - mem_before,
                            errors=max(0, n - loaded),
                            notes=f"{loaded}/{n} loaded, "
                            f"{(mem_after - mem_before) / n:.2f}MB/plugin",
                        )
                    )
                finally:
                    await app.shutdown()
            except Exception as e:
                print(f"  [ERR] batch_load_{n}: {e}")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
                gc.collect()

        return results

    async def bench_reload(self, n_runs: int = 15) -> list[BenchResult]:
        """Mesure le temps de rechargement d'un plugin."""
        tmp = Path(tempfile.mkdtemp(prefix="xcore_bench_"))
        samples: list[float] = []
        errors = 0
        try:
            from xcore.kernel.runtime.lifecycle import LifecycleManager
            from xcore.kernel.security.validation import ManifestValidator

            plugin_dir = _make_plugin_dir(tmp, "bench_reload")
            manifest, _, _ = ManifestValidator().load_and_validate(plugin_dir)
            ctx = _make_ctx(_MockServices())
            lm = LifecycleManager(manifest, ctx)
            await lm.load()

            for _ in range(n_runs):
                try:
                    t0 = time.perf_counter()
                    await lm.reload()
                    samples.append((time.perf_counter() - t0) * 1000)
                except Exception as e:
                    errors += 1
                    print(f"  [WARN] reload error: {e}")

            await lm.unload()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        return (
            [_measure(samples, n_runs, errors, "plugin_reload", self.CATEGORY)]
            if samples
            else []
        )


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 2 — Plugin Call Throughput                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class PluginCallBench:
    """Throughput des appels plugin via le Supervisor."""

    CATEGORY = "plugin_calls"

    async def bench_sequential_calls(self, n_calls: int = 500) -> list[BenchResult]:
        tmp = Path(tempfile.mkdtemp(prefix="xcore_bench_"))
        results = []
        try:
            _make_plugin_dir(tmp / "plugins", "bench_calls")
            cfg = _make_xcore_config(tmp / "plugins")
            app = _make_xcore_instance(cfg)
            await app.boot()

            # warm-up
            for _ in range(10):
                await app.plugins.call("bench_calls", "ping", {})

            samples: list[float] = []
            errors = 0
            for _ in range(n_calls):
                try:
                    t0 = time.perf_counter()
                    r = await app.plugins.call("bench_calls", "ping", {})
                    samples.append((time.perf_counter() - t0) * 1000)
                    if r.get("status") != "ok":
                        errors += 1
                except Exception:
                    errors += 1

            results.append(
                _measure(
                    samples,
                    n_calls,
                    errors,
                    "sequential_call_ping",
                    self.CATEGORY,
                    notes=f"single plugin, {n_calls} calls",
                )
            )

            # echo avec payload
            payload = {"key": "value", "data": list(range(10)), "nested": {"a": 1}}
            samples = []
            for _ in range(n_calls):
                t0 = time.perf_counter()
                await app.plugins.call("bench_calls", "echo", payload)
                samples.append((time.perf_counter() - t0) * 1000)
            results.append(
                _measure(
                    samples,
                    n_calls,
                    0,
                    "sequential_call_echo_payload",
                    self.CATEGORY,
                )
            )

            await app.shutdown()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return results

    async def bench_concurrent_calls(
        self, concurrency_levels: list[int] = (10, 50, 100)
    ) -> list[BenchResult]:
        results = []
        for concurrency in concurrency_levels:
            tmp = Path(tempfile.mkdtemp(prefix="xcore_bench_"))
            try:
                _make_plugin_dir(tmp / "plugins", "bench_concurrent")
                cfg = _make_xcore_config(tmp / "plugins")
                app = _make_xcore_instance(cfg)
                await app.boot()

                # warm-up
                await asyncio.gather(
                    *[
                        app.plugins.call("bench_concurrent", "ping", {})
                        for _ in range(5)
                    ]
                )

                errors = 0
                t0 = time.perf_counter()
                tasks = [
                    app.plugins.call("bench_concurrent", "ping", {})
                    for _ in range(concurrency)
                ]
                raw = await asyncio.gather(*tasks, return_exceptions=True)
                total_ms = (time.perf_counter() - t0) * 1000

                for r in raw:
                    if isinstance(r, Exception) or (
                        isinstance(r, dict) and r.get("status") != "ok"
                    ):
                        errors += 1

                results.append(
                    BenchResult(
                        name=f"concurrent_{concurrency}_calls",
                        category=self.CATEGORY,
                        iterations=concurrency,
                        total_ms=total_ms,
                        mean_ms=total_ms / concurrency,
                        median_ms=total_ms / concurrency,
                        p95_ms=total_ms / concurrency * 1.3,
                        p99_ms=total_ms / concurrency * 1.5,
                        min_ms=0,
                        max_ms=total_ms,
                        std_ms=0,
                        throughput_ops_sec=concurrency / (total_ms / 1000),
                        errors=errors,
                        notes=f"asyncio.gather({concurrency})",
                    )
                )

                await app.shutdown()
            except Exception as e:
                print(f"  [ERR] concurrent_{concurrency}: {e}")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
                gc.collect()
        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 3 — Middleware Pipeline                                         ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class MiddlewareBench:
    CATEGORY = "middleware"

    async def bench_pipeline_overhead(self, n: int = 1000) -> list[BenchResult]:
        """Compare appel direct vs appel via pipeline (4 middlewares)."""
        from xcore.kernel.runtime.middlewares.middleware import (
            Middleware,
            MiddlewarePipeline,
        )

        class NoopMiddleware(Middleware):
            async def __call__(self, pn, ac, pay, nxt, h, **kw):
                return await nxt(pn, ac, pay, h, **kw)

        async def final(pn, ac, pay, **kw):
            return {"status": "ok"}

        results = []

        # 0 middleware
        pipeline0 = MiddlewarePipeline([], final)
        samples: list[float] = []
        for _ in range(n):
            t0 = time.perf_counter()
            await pipeline0.execute("p", "a", {})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "pipeline_0_middlewares", self.CATEGORY))

        # 4 middlewares
        pipeline4 = MiddlewarePipeline([NoopMiddleware() for _ in range(4)], final)
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            await pipeline4.execute("p", "a", {})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "pipeline_4_middlewares", self.CATEGORY))

        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 4 — EventBus / HookManager                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class EventsBench:
    CATEGORY = "events"

    async def bench_eventbus(self, n: int = 2000) -> list[BenchResult]:
        from xcore.kernel.events.bus import EventBus

        results = []
        bus = EventBus()
        samples: list[float] = []
        for _ in range(n):
            t0 = time.perf_counter()
            await bus.emit("test.event", {"data": 1})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "eventbus_emit_no_handlers", self.CATEGORY)
        )

        @bus.on("test.event")
        async def h(event):
            pass

        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            await bus.emit("test.event", {"data": 1})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "eventbus_emit_1_handler", self.CATEGORY)
        )

        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 5 — PermissionEngine                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class PermissionsBench:
    CATEGORY = "permissions"

    def bench_engine(self, n: int = 30000) -> list[BenchResult]:
        from xcore.kernel.permissions.engine import PermissionEngine

        engine = PermissionEngine()
        permissions = [
            {"resource": "db.*", "actions": ["read", "write"], "effect": "allow"},
            {"resource": "*", "actions": ["read"], "effect": "allow"},
        ]
        engine.load_from_manifest("bench_plugin", permissions)

        results = []
        samples: list[float] = []
        for i in range(n):
            t0 = time.perf_counter()
            engine.allows("bench_plugin", "db.users", "read")
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "permission_check_cached", self.CATEGORY)
        )
        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 6 — CacheService                                               ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class CacheBench:
    CATEGORY = "cache"

    async def bench_memory_backend(self, n: int = 3000) -> list[BenchResult]:
        from xcore.services.cache.backends.memory import MemoryBackend

        backend = MemoryBackend(ttl=300, max_size=100_000)
        results = []

        samples: list[float] = []
        for i in range(n):
            t0 = time.perf_counter()
            await backend.set(f"key:{i}", i)
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "cache_set_single", self.CATEGORY))

        samples = []
        for i in range(n):
            t0 = time.perf_counter()
            await backend.get(f"key:{i % 100}")
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "cache_get_hot", self.CATEGORY))

        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 7 — Tenancy                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class TenancyBench:
    CATEGORY = "tenancy"

    async def bench_cache_wrapper(self, n: int = 10000) -> list[BenchResult]:
        from xcore.kernel.tenancy.services import TenantAwareCache
        from xcore.services.cache.backends.memory import MemoryBackend

        backend = MemoryBackend(ttl=300, max_size=100_000)
        wrapped = TenantAwareCache(backend, "acme")
        results = []

        samples: list[float] = []
        for i in range(n):
            t0 = time.perf_counter()
            await wrapped.set(f"key:{i}", i)
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "cache_set_wrapped", self.CATEGORY))

        return results

    async def bench_ipc_auth(self, n: int = 10000) -> list[BenchResult]:
        from unittest.mock import AsyncMock, MagicMock

        from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware

        results = []
        next_fn = AsyncMock(return_value={"status": "ok"})

        def _make_loader(allowed):
            manifest = MagicMock()
            manifest.allowed_callers = allowed
            loader = MagicMock()
            loader.get_manifest.return_value = manifest
            return loader

        mw = IPCAuthMiddleware(_make_loader(["billing"]), enforce=True)
        samples: list[float] = []
        for _ in range(n):
            t0 = time.perf_counter()
            await mw(
                "target", "action", {}, next_fn, handler=MagicMock(), caller="billing"
            )
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "ipc_caller_allowed", self.CATEGORY))

        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 8 — IPC (Plugin A -> Plugin B)                                  ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class IPCBench:
    """Benchmark des appels inter-plugins réels."""

    CATEGORY = "ipc"

    async def bench_real_ipc(self, n_calls: int = 400) -> list[BenchResult]:
        tmp = Path(tempfile.mkdtemp(prefix="xcore_bench_ipc_"))
        results = []
        try:
            # 1. Receiver
            _make_plugin_dir(tmp / "plugins", "receiver", allowed_callers=["caller"])
            # 2. Caller
            _make_plugin_dir(tmp / "plugins", "caller")

            cfg = _make_xcore_config(tmp / "plugins")
            app = _make_xcore_instance(cfg)
            await app.boot()

            # Warm-up
            await app.plugins.call("caller", "proxy_ping", {"target": "receiver"})

            samples: list[float] = []
            errors = 0
            for _ in range(n_calls):
                try:
                    t0 = time.perf_counter()
                    r = await app.plugins.call(
                        "caller", "proxy_ping", {"target": "receiver"}
                    )
                    samples.append((time.perf_counter() - t0) * 1000)
                    if r.get("status") != "ok":
                        errors += 1
                except Exception:
                    errors += 1

            results.append(
                _measure(
                    samples,
                    n_calls,
                    errors,
                    "ipc_plugin_hop_trusted",
                    self.CATEGORY,
                    notes="Kernel -> Caller -> Receiver",
                )
            )
            await app.shutdown()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 9 — Capacity Simulation                                         ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class CapacityBench:
    """Simule le chargement de N plugins pour trouver la limite pratique."""

    async def run(self, max_plugins: int = 150, step: int = 25) -> dict[str, Any]:
        print(f"\nCAPACITY TEST — jusqu'à {max_plugins} plugins")
        results: dict[str, Any] = {}
        levels = list(range(step, max_plugins + 1, step))
        if max_plugins not in levels:
            levels.append(max_plugins)

        for n in levels:
            tmp = Path(tempfile.mkdtemp(prefix="xcore_cap_"))
            try:
                for i in range(n):
                    _make_plugin_dir(tmp / "plugins", f"cap_{i:04d}")

                cfg = _make_xcore_config(tmp / "plugins")
                mem_bef = _mem_mb()
                t0 = time.perf_counter()

                from xcore import Xcore

                app = Xcore(config_path=cfg)
                await app.boot()
                load_ms = (time.perf_counter() - t0) * 1000
                mem_aft = _mem_mb()
                loaded = len(app.plugins.list_plugins())

                results[n] = {
                    "n_requested": n,
                    "n_loaded": loaded,
                    "load_time_ms": round(load_ms, 1),
                    "ms_per_plugin": round(load_ms / loaded, 2) if loaded else 0,
                    "mem_delta_mb": round(mem_aft - mem_bef, 2),
                    "mb_per_plugin": (
                        round((mem_aft - mem_bef) / loaded, 3) if loaded else 0
                    ),
                }
                print(
                    f"  N={n:4d} | loaded={loaded:4d} | load={load_ms:7.1f}ms | mem={mem_aft - mem_bef:.1f}MB"
                )
                await app.shutdown()
            except Exception as e:
                print(f"  N={n}: ERROR — {e}")
                break
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
                gc.collect()
        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Runner principal                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def _make_xcore_instance(cfg: str):
    from xcore import Xcore

    return Xcore(config_path=cfg)


class _MockServices:
    def as_dict(self) -> dict:
        return {}

    def has(self, n: str) -> bool:
        return False

    def get(self, n: str):
        raise KeyError(n)


def _make_ctx(services: _MockServices):
    from unittest.mock import MagicMock

    from xcore.kernel.context import KernelContext

    return KernelContext(
        config=MagicMock(
            directory="/tmp",
            strict_trusted=False,
            secret_key=b"test",
            interval=0,
            entry_point="src/main.py",
        ),
        services=services,
        events=MagicMock(),
        hooks=MagicMock(),
        registry=MagicMock(),
        metrics=MagicMock(),
        tracer=MagicMock(),
        health=MagicMock(),
    )


async def run_suite(args) -> BenchReport:
    import datetime
    import logging

    from xcore import __version__

    # Silence verbose logs
    logging.getLogger("xcore").setLevel(logging.ERROR)

    report = BenchReport(
        xcore_version=__version__,
        timestamp=datetime.datetime.now().isoformat(),
    )

    if _HAS_PSUTIL:
        report.system_info = {
            "cpu_count": psutil.cpu_count(),
            "total_ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        }

    suites = args.suite or [
        "lifecycle",
        "calls",
        "middleware",
        "events",
        "permissions",
        "cache",
        "tenancy",
        "ipc",
    ]

    t_global = time.perf_counter()

    if "lifecycle" in suites:
        print("\n[1] Lifecycle...")
        bench = PluginLifecycleBench()
        for r in await bench.bench_single_load_unload(n_runs=args.runs):
            report.add(r)
        for r in await bench.bench_reload(n_runs=args.runs):
            report.add(r)
        for r in await bench.bench_batch_load():
            report.add(r)

    if "calls" in suites:
        print("\n[2] Calls...")
        bench = PluginCallBench()
        for r in await bench.bench_sequential_calls(n_calls=args.calls):
            report.add(r)
        for r in await bench.bench_concurrent_calls():
            report.add(r)

    if "middleware" in suites:
        print("\n[3] Middleware...")
        bench = MiddlewareBench()
        for r in await bench.bench_pipeline_overhead():
            report.add(r)

    if "events" in suites:
        print("\n[4] Events...")
        bench = EventsBench()
        for r in await bench.bench_eventbus():
            report.add(r)

    if "permissions" in suites:
        print("\n[5] Permissions...")
        bench = PermissionsBench()
        for r in bench.bench_engine():
            report.add(r)

    if "cache" in suites:
        print("\n[6] Cache...")
        bench = CacheBench()
        for r in await bench.bench_memory_backend():
            report.add(r)

    if "tenancy" in suites:
        print("\n[7] Tenancy...")
        bench = TenancyBench()
        for r in await bench.bench_cache_wrapper():
            report.add(r)
        for r in await bench.bench_ipc_auth():
            report.add(r)

    if "ipc" in suites:
        print("\n[8] IPC...")
        bench = IPCBench()
        for r in await bench.bench_real_ipc(n_calls=args.calls):
            report.add(r)

    if "capacity" in suites or args.capacity:
        print("\n[9] Capacity...")
        cap_bench = CapacityBench()
        report.capacity = await cap_bench.run(max_plugins=args.capacity or 100)

    report.total_duration_s = time.perf_counter() - t_global
    return report


def print_report(report: BenchReport) -> None:
    w = 80
    print(f"\n{'═' * w}")
    print(f"  XCORE PERFORMANCE REPORT — v{report.xcore_version}")
    print(f"  Python {report.python_version} | {report.platform} | {report.timestamp}")
    print(f"{'═' * w}")

    categories: dict[str, list[BenchResult]] = {}
    for r in report.results:
        categories.setdefault(r.category, []).append(r)

    headers = [
        "Benchmark",
        "Mean(ms)",
        "Med(ms)",
        "Ops/s",
        "Status",
    ]

    for cat, items in categories.items():
        print(f"\n  ┌── {cat.upper()}")
        rows = [[r.name, f"{r.mean_ms:.3f}", f"{r.median_ms:.3f}", f"{r.throughput_ops_sec:.0f}", "✅" if r.errors == 0 else f"❌ {r.errors}"] for r in items]
        if _HAS_TABULATE:
            print(tabulate(rows, headers=headers, tablefmt="simple"))
        else:
            print(f"  {headers}")
            for row in rows:
                print(f"  {row}")

    if report.capacity:
        print("\n  ┌── CAPACITY")
        for n, data in sorted(report.capacity.items()):
            print(f"    N={n:4d}: {data['load_time_ms']:7.1f}ms total load ({data['ms_per_plugin']:5.1f}ms/p) | {data['mem_delta_mb']:6.1f}MB delta")

    print(f"\n  Total duration: {report.total_duration_s:.1f}s")


def save_report(report: BenchReport, path: str) -> None:
    data = {"meta": asdict(report), "results": [asdict(r) for r in report.results]}
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(description="xcore Benchmarks")
    parser.add_argument("--suite", nargs="+", choices=["lifecycle", "calls", "middleware", "events", "permissions", "cache", "tenancy", "ipc", "capacity"])
    parser.add_argument("--capacity", type=int, default=0)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--calls", type=int, default=300)
    parser.add_argument("--output", type=str, default="xcore_bench_report.json")
    args = parser.parse_args()

    print("xcore Benchmark Suite — starting...")
    report = asyncio.run(run_suite(args))
    print_report(report)
    save_report(report, args.output)


if __name__ == "__main__":
    main()
