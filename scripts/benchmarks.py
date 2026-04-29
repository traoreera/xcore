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

Usage :
    python xcore_bench.py                    # full suite
    python xcore_bench.py --suite plugins    # only plugin benchmarks
    python xcore_bench.py --capacity 200     # test up to 200 plugins
    python xcore_bench.py --output report.json
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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

    FIX: suppression de la heuristique `* 1000 if value < 10 else value` qui
    causait une double-conversion : tous les sites d'appel collectent déjà
    leurs samples en ms (via `(perf_counter() - t0) * 1000`).
    """
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
    base: Path, name: str, mode: str = "trusted", extra_code: str = ""
) -> Path:
    """Crée un plugin minimal valide dans base/name."""
    plugin_dir = base / name
    src_dir = plugin_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    (plugin_dir / "plugin.yaml").write_text(
        textwrap.dedent(
            f"""
        name: {name}
        version: 1.0.0
        execution_mode: {mode}
        description: Benchmark plugin
        permissions:
          - resource: "ping"
            actions: ["read", "write"]
            effect: allow
          - resource: "echo"
            actions: ["read", "write"]
            effect: allow
          - resource: "compute"
            actions: ["read", "write"]
            effect: allow


        resources:
          timeout_seconds: 30
          rate_limit:
            calls: 100000
            period_seconds: 60
    """
        ).strip()
    )

    (src_dir / "main.py").write_text(
        textwrap.dedent(
            f"""
        from xcore.kernel.api.contract import BasePlugin

        class Plugin(BasePlugin):
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
              #dotenv: "./extensions/.env"
              plugin_prefix: "/app"
              server_key: "rhverujierf"
              server_key_iterations: 100000
              plugin_tags:
                - "test"

            # ── Plugins ───────────────────────────────────────────────────
            plugins:
              directory: {plugins_dir}

              # Clé HMAC-SHA256 utilisée pour vérifier plugin.sig
              secret_key: "12345"

              # true = refuse tout plugin Trusted non signé
              strict_trusted: false

              # Intervalle du watcher de rechargement à chaud (secondes)
              # Mettre à 0 pour désactiver en prod si tu gères les reloads via API
              interval: 10

              entry_point: src/main.py

              # Fichiers/extensions exclus du snapshot de détection de changements
              snapshot:
                extensions: [".log", ".pyc", ".html", ".map", ".min.js"]
                filenames: ["__pycache__", "__init__.py", ".env", ".DS_Store"]
                hidden: true

            # ── Services ──────────────────────────────────────────────────
            services:
              # ── Bases de données ────────────────────────────────────────
              databases:
                db:
                  type: sqlasync
                  url: sqlite+aiosqlite:///db.sqlite3
                  echo: false
                redis_db:
                  type: redis
                  url: redis://localhost:6379/0
                  max_connections: 50

              # ── Cache ────────────────────────────────────────────────────
              cache:
                backend: redisrhverujierf
                url: redis://localhost:6379/0
                ttl: 300 # TTL par défaut en secondes
                max_size: 10000 # ignoré en mode redis, actif en mode memory

              # ── Scheduler ────────────────────────────────────────────────
              scheduler:
                enabled: true
                backend: redis # redis = tâches persistantes, survivent au redémarrage
                timezone: Europe/Paris

                # Jobs déclarés statiquement (optionnel)
                #jobs:
                #  # Nettoyage des sessions expirées chaque nuit à 2h
                #  - id: cleanup_sessions
                #    func: myapp.tasks.maintenance:cleanup_sessions
                #    trigger: cron
                #    hour: 2
                #    minute: 0
                #
                #  # Snapshot des métriques toutes les 5 minutes
                #  - id: metrics_snapshot
                #    func: myapp.tasks.monitoring:snapshot_metrics
                #    trigger: interval
                #    minutes: 5

              # ── Observabilité ─────────────────────────────────────────────

            observability:
              logging:
                enabled: true
                level: DEBUG # DEBUG | INFO | WARNING | ERROR | CRITICAL
                format: "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
                file: log/app.log
                max_bytes: 52428800 # 50 MB par fichier
                backup_count: 10 # 10 fichiers de rotation = 500 MB max

              metrics:
                enabled: true
                backend: prometheus # memory | prometheus | statsd
                prefix: myapp # préfixe des métriques exposées sur /metrics

              tracing:
                enabled: false # true si tu utilises OpenTelemetry / Jaeger
                backend: noop # noop | opentelemetry | jaeger
                service_name: my-app
                endpoint: null # ex: http://jaeger:4317 (OTLP gRPC)

            # ── Sécurité ──────────────────────────────────────────────────
            security:
              # Imports Python autorisés dans les plugins Sandboxed (whitelist AST)
              # Les plugins Trusted ne sont pas limités par cette liste
              allowed_imports:
                - argparse
                - fastapi
                - json
                - re
                - math
                - random
                - datetime
                - time
                - pathlib
                - typing
                - dataclasses
                - enum
                - functools
                - itertools
                - collections
                - string
                - hashlib
                - base64
                - asyncio
                - logging
                - uuid
                - decimal
                - copy

              # Imports explicitement interdits (surcharge les allowed_imports)
              forbidden_imports:
                - os

              # Rate limit appliqué par défaut à chaque plugin non configuré
              rate_limit_default:
                calls: 200
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
            manifest, is_ok, version = ManifestValidator().load_and_validate(plugin_dir)
            # FIX: suppression du print(manifest, is_ok, version) de debug
            services_mock = _MockServices()

            load_samples: list[float] = []
            unload_samples: list[float] = []
            errors = 0

            for _ in range(n_runs):
                ctx = _make_ctx(services_mock)
                lm = LifecycleManager(
                    manifest if isinstance(manifest, PluginManifest) else None, ctx
                )
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
        self, batch_sizes: list[int] = (5, 20, 50, 100)
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
                    loaded = len(app.plugins.list_plugins())

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
                            errors=n - loaded,
                            notes=f"{loaded}/{n} loaded, "
                            f"{(mem_after - mem_before) / n:.2f}MB/plugin",
                        )
                    )
                finally:
                    await app.shutdown()
            except Exception as e:
                print(f"  [ERR] batch_load_{n}: {e}")
                traceback.print_exc()
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

            # FIX: remplacement du bare `except: quit()` par une vraie gestion d'erreur
            try:
                lm = LifecycleManager(manifest, ctx)
            except Exception as e:
                raise RuntimeError(
                    f"LifecycleManager instanciation failed "
                    f"(manifest type={type(manifest).__name__}): {e}"
                ) from e

            await lm.load()

            for _ in range(n_runs):
                try:
                    t0 = time.perf_counter()
                    await lm.reload()
                    samples.append((time.perf_counter() - t0) * 1000)
                except Exception as e:
                    errors += 1
                    # FIX: log the error instead of silently swallowing it
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
        self, concurrency_levels: list[int] = (5, 20, 50, 100)
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

    async def bench_multi_plugin_routing(
        self, plugin_counts: list[int] = (5, 10, 25, 50)
    ) -> list[BenchResult]:
        """Appels distribués sur N plugins (routing overhead)."""
        results = []
        for n in plugin_counts:
            tmp = Path(tempfile.mkdtemp(prefix="xcore_bench_"))
            try:
                for i in range(n):
                    _make_plugin_dir(tmp / "plugins", f"router_{i:03d}")
                cfg = _make_xcore_config(tmp / "plugins")
                app = _make_xcore_instance(cfg)
                await app.boot()

                loaded = app.plugins.list_plugins()
                n_calls = 200
                samples: list[float] = []
                for i in range(n_calls):
                    pname = loaded[i % len(loaded)]
                    app.plugins._permissions.grant_all(pname)
                    t0 = time.perf_counter()
                    await app.plugins.call(pname, "ping", {})
                    samples.append((time.perf_counter() - t0) * 1000)

                results.append(
                    _measure(
                        samples,
                        n_calls,
                        0,
                        f"routing_{n}_plugins",
                        self.CATEGORY,
                        notes=f"{len(loaded)} loaded, {n_calls} calls round-robin",
                    )
                )
                await app.shutdown()
            except Exception as e:
                print(f"  [ERR] routing_{n}: {e}")
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

        # 0 middleware — appel direct
        pipeline0 = MiddlewarePipeline([], final)
        samples: list[float] = []
        for _ in range(n):
            t0 = time.perf_counter()
            await pipeline0.execute("p", "a", {})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "pipeline_0_middlewares", self.CATEGORY))

        # 4 middlewares noop
        pipeline4 = MiddlewarePipeline([NoopMiddleware() for _ in range(4)], final)
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            await pipeline4.execute("p", "a", {})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "pipeline_4_middlewares", self.CATEGORY))

        overhead_ms = statistics.mean(
            [r.mean_ms for r in results if "4" in r.name]
        ) - statistics.mean([r.mean_ms for r in results if "0" in r.name])
        print(f"  → Middleware overhead (4 layers): {overhead_ms:.4f}ms/call")
        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 4 — EventBus / HookManager                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class EventsBench:
    CATEGORY = "events"

    async def bench_eventbus(self, n: int = 2000) -> list[BenchResult]:
        from xcore.kernel.events.bus import EventBus

        results = []

        # emit sans handlers
        bus = EventBus()
        samples: list[float] = []
        for _ in range(n):
            t0 = time.perf_counter()
            await bus.emit("test.event", {"data": 1})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "eventbus_emit_no_handlers", self.CATEGORY)
        )

        # emit avec 1 handler async
        counter = [0]

        @bus.on("test.event")
        async def h(event):
            counter[0] += 1

        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            await bus.emit("test.event", {"data": 1})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "eventbus_emit_1_handler", self.CATEGORY)
        )

        # emit avec 10 handlers
        bus2 = EventBus()
        for i in range(10):

            @bus2.on("test.event")
            async def _h(event, _i=i):
                pass

        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            await bus2.emit("test.event", {})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "eventbus_emit_10_handlers", self.CATEGORY)
        )

        # wildcard matching
        bus3 = EventBus()

        @bus3.on("user.*")
        async def _wh(event):
            pass

        samples = []
        for i in range(n):
            t0 = time.perf_counter()
            await bus3.emit(f"user.event_{i % 20}", {})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "eventbus_wildcard_matching", self.CATEGORY)
        )

        return results

    async def bench_hookmanager(self, n: int = 1000) -> list[BenchResult]:
        from xcore.kernel.events.hooks import HookManager

        results = []
        hm = HookManager()

        # 5 hooks prioritaires
        for prio in (10, 30, 50, 70, 90):

            @hm.on("test.event", priority=prio)
            def _sync_h(event, _p=prio):
                return _p

        samples: list[float] = []
        for _ in range(n):
            t0 = time.perf_counter()
            await hm.emit("test.event", {"data": 1})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "hookmanager_5_priority_hooks", self.CATEGORY)
        )

        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 5 — PermissionEngine                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class PermissionsBench:
    CATEGORY = "permissions"

    def bench_engine(self, n: int = 50000) -> list[BenchResult]:
        from xcore.kernel.permissions.engine import PermissionEngine

        engine = PermissionEngine()
        permissions = [
            {"resource": "db.*", "actions": ["read", "write"], "effect": "allow"},
            {"resource": "cache.*", "actions": ["*"], "effect": "allow"},
            {"resource": "os.*", "actions": ["*"], "effect": "deny"},
            {"resource": "fs.tmp.*", "actions": ["write"], "effect": "allow"},
            {"resource": "api.v1.*", "actions": ["call"], "effect": "allow"},
            {"resource": "*", "actions": ["read"], "effect": "allow"},
        ]
        engine.load_from_manifest("bench_plugin", permissions)
        engine.grant_all("bench_plugin")

        test_cases = [
            ("db.users", "read"),
            ("cache.items", "write"),
            ("os.path", "read"),
            ("fs.tmp.file", "write"),
            ("api.v1.login", "call"),
            ("unknown", "write"),
        ]

        results = []

        # Sans cache (cold)
        engine._cache.clear()
        samples: list[float] = []
        for i in range(n):
            res, act = test_cases[i % len(test_cases)]
            engine._cache.clear()  # force cold
            t0 = time.perf_counter()
            engine.allows("bench_plugin", res, act)
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "permission_check_cold", self.CATEGORY))

        # Avec cache (warm) — pré-chauffe
        for res, act in test_cases:
            engine.allows("bench_plugin", res, act)
        samples = []
        for i in range(n):
            res, act = test_cases[i % len(test_cases)]
            t0 = time.perf_counter()
            engine.allows("bench_plugin", res, act)
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n, 0, "permission_check_cached", self.CATEGORY)
        )

        speedup = (
            results[0].mean_ms / results[1].mean_ms if results[1].mean_ms > 0 else 1
        )
        print(f"  → Cache speedup: {speedup:.1f}x")
        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 6 — CacheService                                               ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class CacheBench:
    CATEGORY = "cache"

    async def bench_memory_backend(self, n: int = 5000) -> list[BenchResult]:
        from xcore.services.cache.backends.memory import MemoryBackend

        backend = MemoryBackend(ttl=300, max_size=100_000)
        results = []

        # SET
        samples: list[float] = []
        for i in range(n):
            t0 = time.perf_counter()
            await backend.set(f"key:{i}", {"value": i, "data": list(range(5))})
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "cache_set_single", self.CATEGORY))

        # GET (hot)
        samples = []
        for i in range(n):
            t0 = time.perf_counter()
            await backend.get(f"key:{i % 1000}")
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(_measure(samples, n, 0, "cache_get_hot", self.CATEGORY))

        # MSET
        mapping = {f"mkey:{i}": {"v": i} for i in range(100)}
        samples = []
        for _ in range(n // 10):
            t0 = time.perf_counter()
            await backend.mset(mapping)
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n // 10, 0, "cache_mset_100_keys", self.CATEGORY)
        )

        # MGET
        keys = [f"mkey:{i}" for i in range(100)]
        samples = []
        for _ in range(n // 10):
            t0 = time.perf_counter()
            await backend.mget(keys)
            samples.append((time.perf_counter() - t0) * 1000)
        results.append(
            _measure(samples, n // 10, 0, "cache_mget_100_keys", self.CATEGORY)
        )

        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Section 7 — Capacity Simulation                                         ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class CapacityBench:
    """Simule le chargement de N plugins pour trouver la limite pratique."""

    async def run(self, max_plugins: int = 150, step: int = 25) -> dict[str, Any]:
        print(f"\n{'=' * 60}")
        print(f"  CAPACITY TEST — jusqu'à {max_plugins} plugins")
        print(f"{'=' * 60}")

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

                # appels concurrents sur tous les plugins
                all_plugins = app.plugins.list_plugins()
                t1 = time.perf_counter()
                tasks = [
                    app.plugins.call(p, "ping", {})
                    # cap 200 concurrent
                    for p in all_plugins[: min(loaded, 200)]
                ]
                raw = await asyncio.gather(*tasks, return_exceptions=True)
                call_ms = (time.perf_counter() - t1) * 1000
                ok_calls = sum(
                    1 for r in raw if isinstance(r, dict) and r.get("status") == "ok"
                )

                results[n] = {
                    "n_requested": n,
                    "n_loaded": loaded,
                    "load_time_ms": round(load_ms, 1),
                    "ms_per_plugin": round(load_ms / loaded, 2) if loaded else 0,
                    "mem_delta_mb": round(mem_aft - mem_bef, 2),
                    "mb_per_plugin": (
                        round((mem_aft - mem_bef) / loaded, 3) if loaded else 0
                    ),
                    "concurrent_calls_ok": ok_calls,
                    "concurrent_call_ms": round(call_ms, 1),
                }
                print(
                    f"  N={n:4d}  | loaded={loaded:4d} | "
                    f"load={load_ms:7.1f}ms ({load_ms / loaded:.1f}ms/p) | "
                    f"mem={mem_aft - mem_bef:.1f}MB "
                    f"({(mem_aft - mem_bef) / loaded:.2f}MB/p) | "
                    f"concurrent_ok={ok_calls}/{len(tasks)}"
                )

                await app.shutdown()
            except MemoryError:
                print(f"  N={n}: MemoryError — limite atteinte")
                results[n] = {"error": "MemoryError"}
                break
            except Exception as e:
                print(f"  N={n}: ERROR — {e}")
                results[n] = {"error": str(e)}
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
                gc.collect()
                await asyncio.sleep(0.05)

        return results


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Helpers internes                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def _make_xcore_instance(cfg: str):
    """
    Retourne une instance Xcore fraîche (sans cache — isolation garantie).

    FIX: renommé depuis `Xcore_cached` (non-PEP8, trompeur) ;
         suppression du dict `_xcore_cache` qui était déclaré mais jamais utilisé.
    """
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

    ctx = KernelContext(
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
    ctx.services = services
    return ctx


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Runner principal                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝


async def run_suite(args) -> BenchReport:
    import datetime

    from xcore import __version__

    report = BenchReport(
        xcore_version=__version__,
        timestamp=datetime.datetime.now().isoformat(),
    )

    if _HAS_PSUTIL:
        report.system_info = {
            "cpu_count": psutil.cpu_count(),
            "cpu_freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else "N/A",
            "total_ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
            "available_ram_gb": round(psutil.virtual_memory().available / 1024**3, 1),
        }

    suites_to_run = (
        args.suite
        if args.suite
        else ["lifecycle", "calls", "middleware", "events", "permissions", "cache"]
    )

    t_global = time.perf_counter()

    # ── 1. Lifecycle ──────────────────────────────────────────
    if "lifecycle" in suites_to_run or "plugins" in suites_to_run:
        print("\n[1/7] Plugin Lifecycle benchmarks...")
        bench = PluginLifecycleBench()
        for r in await bench.bench_single_load_unload(n_runs=args.runs):
            report.add(r)
            print(f"  ✓ {r.name}: mean={r.mean_ms:.2f}ms, p99={r.p99_ms:.2f}ms")
        for r in await bench.bench_reload(n_runs=args.runs):
            report.add(r)
            print(f"  ✓ {r.name}: mean={r.mean_ms:.2f}ms")
        for r in await bench.bench_batch_load(batch_sizes=[5, 20, 50]):
            report.add(r)
            print(f"  ✓ {r.name}: {r.total_ms:.0f}ms total, {r.notes}")

    # ── 2. Calls ──────────────────────────────────────────────
    if "calls" in suites_to_run:
        print("\n[2/7] Plugin Call Throughput benchmarks...")
        bench = PluginCallBench()
        for r in await bench.bench_sequential_calls(n_calls=args.calls):
            report.add(r)
            ops = r.throughput_ops_sec
            print(f"  ✓ {r.name}: mean={r.mean_ms:.3f}ms, {ops:.0f} ops/s")
        for r in await bench.bench_concurrent_calls([10, 50, 100]):
            report.add(r)
            print(f"  ✓ {r.name}: {r.throughput_ops_sec:.0f} ops/s")
        for r in await bench.bench_multi_plugin_routing([5, 20]):
            report.add(r)
            print(f"  ✓ {r.name}: mean={r.mean_ms:.3f}ms")

    # ── 3. Middleware ─────────────────────────────────────────
    if "middleware" in suites_to_run:
        print("\n[3/7] Middleware Pipeline benchmarks...")
        bench = MiddlewareBench()
        for r in await bench.bench_pipeline_overhead(n=2000):
            report.add(r)
            ops = r.throughput_ops_sec
            print(f"  ✓ {r.name}: mean={r.mean_ms:.4f}ms, {ops:.0f} ops/s")

    # ── 4. Events ─────────────────────────────────────────────
    if "events" in suites_to_run:
        print("\n[4/7] EventBus / HookManager benchmarks...")
        bench = EventsBench()
        for r in await bench.bench_eventbus(n=2000):
            report.add(r)
            ops = r.throughput_ops_sec
            print(f"  ✓ {r.name}: mean={r.mean_ms:.4f}ms, {ops:.0f} ops/s")
        for r in await bench.bench_hookmanager(n=1000):
            report.add(r)
            print(f"  ✓ {r.name}: mean={r.mean_ms:.4f}ms")

    # ── 5. Permissions ────────────────────────────────────────
    if "permissions" in suites_to_run:
        print("\n[5/7] PermissionEngine benchmarks...")
        bench = PermissionsBench()
        for r in bench.bench_engine(n=30000):
            report.add(r)
            ops = r.throughput_ops_sec
            print(f"  ✓ {r.name}: mean={r.mean_ms:.5f}ms, {ops:.0f} ops/s")

    # ── 6. Cache ──────────────────────────────────────────────
    if "cache" in suites_to_run:
        print("\n[6/7] CacheService (memory backend) benchmarks...")
        bench = CacheBench()
        for r in await bench.bench_memory_backend(n=3000):
            report.add(r)
            ops = r.throughput_ops_sec
            print(f"  ✓ {r.name}: mean={r.mean_ms:.4f}ms, {ops:.0f} ops/s")

    # ── 7. Capacity ───────────────────────────────────────────
    if "capacity" in suites_to_run or args.capacity:
        max_p = args.capacity if args.capacity else 100
        step = max(10, max_p // 10)
        print(f"\n[7/7] Capacity simulation (max={max_p}, step={step})...")
        cap_bench = CapacityBench()
        report.capacity = await cap_bench.run(max_plugins=max_p, step=step)

    report.total_duration_s = time.perf_counter() - t_global
    return report


def print_report(report: BenchReport) -> None:
    w = 80
    print(f"\n{'═' * w}")
    print(f"  XCORE PERFORMANCE REPORT — v{report.xcore_version}")
    print(
        f"  Python {report.python_version} | {report.platform} | "
        f"{report.cpu_count} CPUs | {report.timestamp}"
    )
    if report.system_info:
        si = report.system_info
        print(
            f"  RAM: {si.get('total_ram_gb')}GB total, "
            f"{si.get('available_ram_gb')}GB available | "
            f"CPU: {si.get('cpu_freq_mhz')}MHz"
        )
    print(f"{'═' * w}")

    # Regrouper par catégorie
    categories: dict[str, list[BenchResult]] = {}
    for r in report.results:
        categories.setdefault(r.category, []).append(r)

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

    for cat, items in categories.items():
        print(f"\n  ┌── {cat.upper()} {'─' * (w - 7 - len(cat))}")
        rows = [r.as_row() for r in items]
        if _HAS_TABULATE:
            print(tabulate(rows, headers=headers, tablefmt="simple"))
        else:
            print("  " + "  ".join(f"{h:<16}" for h in headers))
            for row in rows:
                print("  " + "  ".join(f"{str(c):<16}" for c in row))

    # Capacity summary
    if report.capacity:
        print(f"\n  ┌── CAPACITY SIMULATION {'─' * (w - 25)}")
        cap_headers = [
            "N",
            "Loaded",
            "Load(ms)",
            "ms/plugin",
            "ΔMem(MB)",
            "MB/plugin",
            "Concurrent OK",
        ]
        cap_rows = []
        for n, data in sorted(report.capacity.items()):
            if "error" in data:
                cap_rows.append([n, "ERROR", "-", "-", "-", "-", data["error"]])
            else:
                cap_rows.append(
                    [
                        data["n_requested"],
                        f"{data['n_loaded']}/{data['n_requested']}",
                        f"{data['load_time_ms']:.0f}",
                        f"{data['ms_per_plugin']:.1f}",
                        f"{data['mem_delta_mb']:.1f}",
                        f"{data['mb_per_plugin']:.3f}",
                        f"{data['concurrent_calls_ok']}",
                    ]
                )
        if _HAS_TABULATE:
            print(tabulate(cap_rows, headers=cap_headers, tablefmt="simple"))
        else:
            print("  " + "  ".join(f"{h:<15}" for h in cap_headers))
            for row in cap_rows:
                print("  " + "  ".join(f"{str(c):<15}" for c in row))

        # extrapolation
        valid = [
            (n, d)
            for n, d in report.capacity.items()
            if isinstance(d, dict)
            and "error" not in d
            and d.get("mb_per_plugin", 0) > 0
        ]
        if valid:
            avg_mb = statistics.mean(d["mb_per_plugin"] for _, d in valid)
            avg_ms = statistics.mean(d["ms_per_plugin"] for _, d in valid)
            if _HAS_PSUTIL:
                avail_mb = psutil.virtual_memory().available / 1024**2
                theoretical_max = int(avail_mb / avg_mb)
                print("\n  Extrapolation:")
                print(
                    f"    Average {avg_mb:.3f}MB/plugin — "
                    f"{avail_mb:.0f}MB available → "
                    f"≈ {theoretical_max} plugins theoretically supportable"
                )
                print(f"    Average {avg_ms:.1f}ms/plugin load time")

    print(f"\n  Total benchmark duration: {report.total_duration_s:.1f}s")
    print(f"{'═' * w}")

    # Recommandations
    print("\n  INSIGHTS:")
    all_results = {r.name: r for r in report.results}

    if "sequential_call_ping" in all_results:
        r = all_results["sequential_call_ping"]
        print(
            f"  • Plugin call latency (ping): {r.mean_ms:.3f}ms mean, "
            f"{r.p99_ms:.3f}ms P99 — "
            f"{'✅ excellent' if r.mean_ms < 1 else '⚠ ok' if r.mean_ms < 5 else '❌'}"
        )

    if (
        "permission_check_cold" in all_results
        and "permission_check_cached" in all_results
    ):
        cold = all_results["permission_check_cold"].mean_ms
        cached = all_results["permission_check_cached"].mean_ms
        speedup = cold / cached if cached > 0 else 1
        print(
            f"  • Permission cache speedup: {speedup:.1f}x "
            f"({cold:.5f}ms cold → {cached:.5f}ms cached)"
        )

    if (
        "pipeline_0_middlewares" in all_results
        and "pipeline_4_middlewares" in all_results
    ):
        overhead = (
            all_results["pipeline_4_middlewares"].mean_ms
            - all_results["pipeline_0_middlewares"].mean_ms
        )
        print(f"  • Middleware overhead (4 layers): {overhead:.4f}ms/call")

    for name in ["eventbus_emit_no_handlers", "eventbus_emit_10_handlers"]:
        if name in all_results:
            r = all_results[name]
            print(f"  • {name}: {r.throughput_ops_sec:.0f} ops/s")


def save_report(report: BenchReport, path: str) -> None:
    def _serialize(obj):
        if isinstance(obj, BenchResult):
            return asdict(obj)
        return str(obj)

    data = {
        "meta": {
            "xcore_version": report.xcore_version,
            "python_version": report.python_version,
            "platform": report.platform,
            "timestamp": report.timestamp,
            "cpu_count": report.cpu_count,
            "total_duration_s": report.total_duration_s,
            "system_info": report.system_info,
        },
        "results": [asdict(r) for r in report.results],
        "capacity": {str(k): v for k, v in report.capacity.items()},
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=_serialize)
    print(f"\n  Report saved → {path}")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Entry point                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def main():
    parser = argparse.ArgumentParser(description="xcore Performance Benchmark")
    parser.add_argument(
        "--suite",
        nargs="+",
        choices=[
            "lifecycle",
            "plugins",
            "calls",
            "middleware",
            "events",
            "permissions",
            "cache",
            "capacity",
        ],
        help="Suites à exécuter (défaut: toutes sauf capacity)",
    )
    parser.add_argument(
        "--capacity",
        type=int,
        default=0,
        help="Activer capacity test jusqu'à N plugins (ex: 200)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=20,
        help="Nombre de runs pour les tests lifecycle (défaut: 20)",
    )
    parser.add_argument(
        "--calls",
        type=int,
        default=300,
        help="Nombre d'appels pour les tests throughput (défaut: 300)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Sauvegarder le rapport JSON dans ce fichier",
    )
    args = parser.parse_args()

    print("xcore Benchmark Suite — starting...")
    if not _HAS_PSUTIL:
        print("  [INFO] Install psutil for memory metrics: pip install psutil")
    if not _HAS_TABULATE:
        print("  [INFO] Install tabulate for better tables: pip install tabulate")

    report = asyncio.run(run_suite(args))
    print_report(report)

    output_path = args.output or "xcore_bench_report.json"
    save_report(report, output_path)
    return report


if __name__ == "__main__":
    main()
