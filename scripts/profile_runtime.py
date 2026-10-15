"""
xcore runtime profiling
=======================
Complements ``scripts/benchmarks.py`` (timing only) with CPU, memory, import
cost and GC measurements on the hot paths of the kernel.

Sub-commands:
    calls     latency of ``plugins.call()`` (best-of-rounds) + cProfile of the hot path
    boot      cold-start time vs. number of plugins (+ optional cProfile)
    memory    tracemalloc growth per call (leak hunt) + allocations after boot
    reload    plugin reload latency, ``sys.modules`` sweep and full-GC pause
    imports   cold import cost of ``xcore`` and of its heavy dependencies
    workers   RSS of live sandboxed workers (Linux, needs ``pgrep``)

Usage:
    python scripts/profile_runtime.py calls --tracing null
    python scripts/profile_runtime.py calls --mode sandboxed --n 1000
    python scripts/profile_runtime.py boot --plugins 50
    python scripts/profile_runtime.py memory --n 10000 --cap spans,ipc,perm
    python scripts/profile_runtime.py reload
    python scripts/profile_runtime.py imports
    python scripts/profile_runtime.py workers --plugins 4

Observability knobs (``--logging``, ``--metrics``, ``--tracing``) let you
isolate what each layer costs on the call path.  ``--tracing null`` runs the
OpenTelemetry SDK with a no-op exporter: it separates the SDK cost from the
export cost (``console`` uses a synchronous SimpleSpanProcessor).

Reading the numbers:
    * Machines are noisy.  Latencies are reported as the best round and the
      median of the rounds' p50 -- trust the best round.
    * cProfile inflates tight loops a lot (a 0.5 ms reload shows up as 28 ms).
      Use it for the *shape* of a profile; trust the un-profiled numbers.
    * For a flame-graph-like view of a running server, use py-spy externally.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import cProfile
import gc
import io
import os
import pstats
import shutil
import statistics
import subprocess
import sys
import tempfile
import textwrap
import time
import tracemalloc
from collections import deque
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import benchmarks as bench  # noqa: E402  (reuses its plugin generator)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Helpers                                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝


@contextlib.contextmanager
def workspace() -> Iterator[Path]:
    """Temp dir used as cwd, so sqlite files and logs never reach the repo."""
    tmp = Path(tempfile.mkdtemp(prefix="xprof_"))
    cwd = Path.cwd()
    os.chdir(tmp)
    try:
        yield tmp
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


def build_config(plugins_dir: Path, args: argparse.Namespace) -> str:
    """Write a minimal integration config and return its path."""
    if args.tracing == "null":
        from opentelemetry.sdk.trace.export import (
            ConsoleSpanExporter,
            SpanExportResult,
        )

        ConsoleSpanExporter.export = lambda self, spans: SpanExportResult.SUCCESS

    tracing_on = str(args.tracing != "off").lower()
    metrics_on = str(args.metrics != "off").lower()
    level = "DEBUG" if args.logging == "debug" else "WARNING"
    cfg_file = plugins_dir.parent / "profile.yaml"
    cfg_file.write_text(textwrap.dedent(f"""
            app:
              name: profile
              env: development
              debug: false
              secret_key: "profile-secret"
              plugin_prefix: "/app"
              server_key: "profile-server-key"
              server_key_iterations: 100000
              plugin_tags: ["profile"]
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
                  url: sqlite+aiosqlite:///{plugins_dir.parent}/db.sqlite3
                  echo: false
              cache:
                backend: memory
                ttl: 300
                max_size: 10000
              scheduler:
                enabled: false
            security:
              allowed_imports: ["*"]
              rate_limit_default:
                calls: 100000
                period_seconds: 60
            observability:
              logging:
                level: {level}
                file: {plugins_dir.parent}/app.log
                output: text
              metrics:
                enabled: {metrics_on}
                backend: prometheus
                prefix: profile
              tracing:
                enabled: {tracing_on}
                backend: opentelemetry
                service_name: profile
                endpoint: null
            """).strip() + "\n")
    return str(cfg_file)


def make_plugins(tmp: Path, args: argparse.Namespace, count: int) -> str:
    for i in range(count):
        bench._make_plugin_dir(tmp / "plugins", f"p{i}", mode=args.mode)
    return build_config(tmp / "plugins", args)


@contextlib.asynccontextmanager
async def booted_app(args: argparse.Namespace, count: int = 1) -> AsyncIterator[Any]:
    from xcore import Xcore

    with workspace() as tmp:
        app = Xcore(config_path=make_plugins(tmp, args, count))
        await app.boot()
        try:
            yield app
        finally:
            await app.shutdown()


def table(pr: cProfile.Profile, sort: str, top: int) -> str:
    out = io.StringIO()
    stats = pstats.Stats(pr, stream=out)
    stats.strip_dirs().sort_stats(sort).print_stats(top)
    return "\n".join(line for line in out.getvalue().splitlines() if line.strip())


def print_profile(pr: cProfile.Profile, top: int) -> None:
    print("\n--- cProfile, by tottime (self time)")
    print(table(pr, "tottime", top))
    print("\n--- cProfile, by cumtime")
    print(table(pr, "cumulative", top))


async def latency_rounds(
    call: Callable[[], Any], rounds: int, per_round: int
) -> list[tuple[float, float, float]]:
    """(p50, mean, p99) in microseconds for each round."""
    result = []
    for _ in range(rounds):
        samples: list[float] = []
        for _ in range(per_round):
            t0 = time.perf_counter()
            await call()
            samples.append((time.perf_counter() - t0) * 1e6)
        samples.sort()
        result.append(
            (
                samples[len(samples) // 2],
                statistics.fmean(samples),
                samples[int(len(samples) * 0.99)],
            )
        )
    return result


def top_allocations(
    snapshot: tracemalloc.Snapshot,
    base: tracemalloc.Snapshot,
    limit: int,
    key: str = "lineno",
) -> None:
    for stat in snapshot.compare_to(base, key)[:limit]:
        frame = stat.traceback[0]
        where = frame.filename if key == "filename" else frame
        print(f"{stat.size_diff / 1024:10.1f} KiB {stat.count_diff:7d} blocks  {where}")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Sub-commands                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════╝


async def cmd_calls(args: argparse.Namespace) -> None:
    async with booted_app(args) as app:

        async def ping() -> None:
            await app.plugins.call("p0", "ping", {})

        for _ in range(50):
            await ping()

        rounds = await latency_rounds(ping, args.rounds, args.per_round)
        best = min(rounds)
        median_p50 = statistics.median(r[0] for r in rounds)
        print(
            f"mode={args.mode} logging={args.logging} metrics={args.metrics} "
            f"tracing={args.tracing}\n"
            f"  best round : p50={best[0]:.1f}us mean={best[1]:.1f}us "
            f"p99={best[2]:.1f}us\n"
            f"  median of the rounds' p50: {median_p50:.1f}us "
            f"({args.rounds} rounds x {args.per_round} calls)"
        )

        if args.no_cprofile:
            return
        profiler = cProfile.Profile()
        profiler.enable()
        for _ in range(args.n):
            await ping()
        profiler.disable()
        print_profile(profiler, args.top)
        if args.callers:
            print(f"\n--- callers of {args.callers!r}")
            pstats.Stats(profiler).strip_dirs().print_callers(args.callers)


async def cmd_boot(args: argparse.Namespace) -> None:
    from xcore import Xcore

    timings: list[float] = []
    for _ in range(args.rounds):
        with workspace() as tmp:
            app = Xcore(config_path=make_plugins(tmp, args, args.plugins))
            t0 = time.perf_counter()
            await app.boot()
            timings.append((time.perf_counter() - t0) * 1000)
            await app.shutdown()
    ordered = sorted(timings)
    print(
        f"boot {args.plugins} {args.mode} plugins: first={timings[0]:.0f}ms "
        f"best={ordered[0]:.0f}ms median={statistics.median(ordered):.0f}ms "
        f"({ordered[0] / args.plugins:.1f}ms/plugin at best)"
    )

    if args.no_cprofile:
        return
    with workspace() as tmp:
        app = Xcore(config_path=make_plugins(tmp, args, args.plugins))
        profiler = cProfile.Profile()
        profiler.enable()
        await app.boot()
        profiler.disable()
        await app.shutdown()
    print_profile(profiler, args.top)


# Containers that grow with the number of calls.  --cap replaces them with a
# 1-slot deque to attribute memory growth (a bisect, not a fix).
_CAPPABLE = {
    "spans": lambda app: setattr(app.tracer, "_spans", deque(maxlen=1)),
    "ipc": lambda app: setattr(app.plugins, "_ipc_audit", deque(maxlen=1)),
    "perm": lambda app: setattr(
        app.plugins._permissions, "_audit_log", deque(maxlen=1)
    ),
}


async def cmd_memory(args: argparse.Namespace) -> None:
    from xcore import Xcore

    with workspace() as tmp:
        app = Xcore(config_path=make_plugins(tmp, args, args.plugins))
        gc.collect()
        tracemalloc.start(25)
        base = tracemalloc.take_snapshot()
        await app.boot()
        gc.collect()
        after_boot = tracemalloc.take_snapshot()
        current, peak = tracemalloc.get_traced_memory()
        print(
            f"boot {args.plugins} {args.mode} plugins: "
            f"current={current / 1e6:.1f}MB peak={peak / 1e6:.1f}MB"
        )
        print("\n--- top allocations after boot (by file)")
        top_allocations(after_boot, base, 8, key="filename")

        for name in filter(None, args.cap.split(",")):
            try:
                _CAPPABLE[name](app)
            except (KeyError, AttributeError) as exc:
                print(f"[WARN] cannot cap {name!r}: {exc!r}")

        await app.plugins.call("p0", "ping", {})
        gc.collect()
        before = tracemalloc.take_snapshot()
        for _ in range(args.n):
            await app.plugins.call("p0", "echo", {"a": 1})
            # Yield so cancelled wait_for timers are purged: without it the
            # loop never turns and they look like a leak.
            await asyncio.sleep(0)
        await asyncio.sleep(0.1)
        gc.collect()
        after = tracemalloc.take_snapshot()

        growth = sum(s.size_diff for s in after.compare_to(before, "lineno"))
        print(
            f"\n--- growth after {args.n} calls (cap={args.cap or 'none'}): "
            f"{growth / 1024:.1f} KiB = {growth / args.n:.0f} B/call"
        )
        spans = getattr(getattr(app, "tracer", None), "_spans", None)
        if spans is not None:
            print(f"len(tracer._spans) = {len(spans)}")
        top_allocations(after, before, args.top)
        await app.shutdown()


async def cmd_reload(args: argparse.Namespace) -> None:
    async with booted_app(args) as app:
        for _ in range(5):
            await app.plugins.reload("p0")
        samples: list[float] = []
        for _ in range(args.n):
            t0 = time.perf_counter()
            await app.plugins.reload("p0")
            samples.append((time.perf_counter() - t0) * 1000)
        samples.sort()
        print(
            f"reload x{args.n}: p50={samples[len(samples) // 2]:.2f}ms "
            f"mean={statistics.fmean(samples):.2f}ms "
            f"p95={samples[int(len(samples) * 0.95)]:.2f}ms max={samples[-1]:.2f}ms"
        )

        # Memory per reload: a flat growth across batches means bounded state
        # (e.g. the EventBus emission log), a constant one means a leak.
        tracemalloc.start(10)
        previous = tracemalloc.take_snapshot()
        for batch in range(3):
            for _ in range(args.n):
                await app.plugins.reload("p0")
            # Let the release watcher run its debounced gc.collect() (1 s).
            await asyncio.sleep(1.2)
            gc.collect()
            current = tracemalloc.take_snapshot()
            grown = sum(s.size_diff for s in current.compare_to(previous, "lineno"))
            print(
                f"memory batch {batch}: {grown / 1024:+.1f} KiB for {args.n} "
                f"reloads = {grown / args.n:.0f} B/reload"
            )
            if batch == 2:
                top_allocations(current, previous, 4)
            previous = current
        tracemalloc.stop()

        prefix = "xcore_plugin_p0."
        passes = 1000
        t0 = time.perf_counter()
        for _ in range(passes):
            for mod in list(sys.modules):
                if mod.startswith(prefix):
                    sys.modules.pop(mod, None)
        per_pass_ms = (time.perf_counter() - t0) * 1000 / passes
        print(
            f"sys.modules sweep ({len(sys.modules)} modules): "
            f"{per_pass_ms:.3f}ms per pass"
        )

        def full_gc() -> tuple[float, float]:
            pauses = []
            for _ in range(7):
                t0 = time.perf_counter()
                gc.collect()
                pauses.append((time.perf_counter() - t0) * 1000)
            return min(pauses), statistics.median(pauses)

        low, med = full_gc()
        print(
            f"full gc.collect() pause (min/median): {low:.1f}/{med:.1f}ms, "
            f"{len(gc.get_objects())} tracked objects"
        )
        # Diagnostic only: freezing AFTER plugins are loaded would hide their
        # reference cycles from the collector and defeat the release watcher.
        gc.freeze()
        low, med = full_gc()
        print(f"after gc.freeze() (min/median): {low:.1f}/{med:.1f}ms")

        if not args.no_cprofile:
            profiler = cProfile.Profile()
            profiler.enable()
            for _ in range(args.n):
                await app.plugins.reload("p0")
            profiler.disable()
            print_profile(profiler, args.top)


def cold_import(statement: str, runs: int) -> tuple[int, int, int]:
    """(min ms, median ms, max RSS MB) of `statement` in fresh interpreters."""
    # Peak RSS comes from VmHWM: ru_maxrss is inherited across fork/exec, so it
    # would report the (large) parent's footprint instead of the child's.
    code = (
        "import time;t=time.perf_counter();"
        f"{statement};ms=int((time.perf_counter()-t)*1000);"
        "hwm=[l for l in open('/proc/self/status') if l.startswith('VmHWM')];"
        "print(ms, int(hwm[0].split()[1])//1024 if hwm else 0)"
    )
    times, rss = [], 0
    for _ in range(runs):
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        ).stdout.split()
        times.append(int(out[0]))
        rss = max(rss, int(out[1]))
    times.sort()
    return times[0], times[len(times) // 2], rss


async def cmd_imports(args: argparse.Namespace) -> None:
    statements = [
        "pass",
        "import pydantic",
        "import fastapi",
        "import celery.app",
        "import sqlalchemy.ext.asyncio",
        "import opentelemetry.sdk.trace",
        "import fastapi, celery.app",
        "import fastapi, sqlalchemy.ext.asyncio",
        "import fastapi, celery.app, sqlalchemy.ext.asyncio",
        "import xcore",
        "import xcore.kernel.sandbox.worker",
    ]
    print(f"cold import, {args.rounds} fresh interpreters each")
    print(f"{'statement':55} {'min ms':>7} {'median':>7} {'RSS MB':>7}")
    for statement in statements:
        low, med, rss = cold_import(statement, args.rounds)
        print(f"{statement:55} {low:7d} {med:7d} {rss:7d}")
    print(
        "\nTip: python -X importtime -c 'import xcore' 2> importtime.txt "
        "shows the full import tree."
    )


def rss_mb(pid: int) -> int:
    with open(f"/proc/{pid}/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) // 1024
    return 0


async def cmd_workers(args: argparse.Namespace) -> None:
    args.mode = "sandboxed"
    from xcore import Xcore

    with workspace() as tmp:
        app = Xcore(config_path=make_plugins(tmp, args, args.plugins))
        t0 = time.perf_counter()
        await app.boot()
        boot_ms = (time.perf_counter() - t0) * 1000
        pids = subprocess.run(
            ["pgrep", "-P", str(os.getpid())], capture_output=True, text=True
        ).stdout.split()
        sizes = [rss_mb(int(pid)) for pid in pids]
        print(
            f"boot {args.plugins} sandboxed plugins: {boot_ms:.0f}ms; "
            f"parent RSS={rss_mb(os.getpid())}MB; {len(pids)} workers "
            f"RSS(MB)={sizes} total={sum(sizes)}MB"
        )
        await app.shutdown()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CLI                                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=["trusted", "sandboxed"], default="trusted")
    common.add_argument("--logging", choices=["off", "debug"], default="off")
    common.add_argument("--metrics", choices=["off", "prometheus"], default="off")
    common.add_argument("--tracing", choices=["off", "null", "console"], default="off")
    common.add_argument("--top", type=int, default=20, help="rows per report")
    common.add_argument("--no-cprofile", action="store_true", help="skip cProfile")

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    calls = sub.add_parser("calls", parents=[common], help="call hot path")
    calls.add_argument("--n", type=int, default=3000, help="profiled calls")
    calls.add_argument("--rounds", type=int, default=7)
    calls.add_argument("--per-round", type=int, default=2000)
    calls.add_argument("--callers", help="print callers of functions matching this")
    calls.set_defaults(func=cmd_calls)

    boot = sub.add_parser("boot", parents=[common], help="cold start")
    boot.add_argument("--plugins", type=int, default=20)
    boot.add_argument("--rounds", type=int, default=5)
    boot.set_defaults(func=cmd_boot)

    memory = sub.add_parser("memory", parents=[common], help="memory growth")
    memory.add_argument("--plugins", type=int, default=3)
    memory.add_argument("--n", type=int, default=10000, help="calls")
    memory.add_argument(
        "--cap",
        default="",
        help="comma list of containers to cap to 1 entry: spans,ipc,perm",
    )
    memory.set_defaults(func=cmd_memory)

    reload_ = sub.add_parser("reload", parents=[common], help="reload + GC pause")
    reload_.add_argument("--n", type=int, default=100)
    reload_.set_defaults(func=cmd_reload)

    imports = sub.add_parser("imports", help="cold import cost")
    imports.add_argument("--rounds", type=int, default=7)
    imports.set_defaults(func=cmd_imports)

    workers = sub.add_parser("workers", parents=[common], help="sandbox worker RSS")
    workers.add_argument("--plugins", type=int, default=4)
    workers.set_defaults(func=cmd_workers)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    # Plain attributes used by shared helpers that not every sub-command defines.
    for name, default in (
        ("mode", "trusted"),
        ("logging", "off"),
        ("metrics", "off"),
        ("tracing", "off"),
    ):
        if not hasattr(args, name):
            setattr(args, name, default)
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
