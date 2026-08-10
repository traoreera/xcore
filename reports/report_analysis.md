## xcore v2.3.2 Benchmark Analysis

### Overview

The benchmark runs on a 6-core machine, 15.3GB RAM, CPU at ~878MHz (likely throttled VM), Python 3.12. Total duration: **280s**, which is long and reflects the complexity of repeated boot/shutdown cycles.

---

### Plugin Lifecycle

**Single load**: mean=3.7ms, p99=49ms — the variance is huge (std=5.4ms, max=57ms). The p99 at 49ms indicates GC spikes or file system contention. The code confirms the issue: `_do_load()` performs `del sys.modules[name]` followed by `spec_from_file_location` + `exec_module` at each iteration. Isolation via namespace (`xcore_plugin_{name}`) is correct but expensive.

**Single unload**: mean=0.35ms — fast and consistent. The cleanup of `sys.modules` is well-scoped.

**Reload**: mean=0.9ms, p99=1.5ms, max=48ms — another unexplained outlier here. Reload executes `_do_unload` + `_do_load` in sequence; the max at 48ms suggests contention during re-import.

**Batch load**: the decreasing trend is good (30ms/plugin at 5, 11ms/plugin at 50), but `errors: -1` is a red flag. Looking at `bench_batch_load` code, `errors = n - loaded` and `loaded = len(app.plugins.list_plugins())`. Obtaining 101 plugins when 100 were requested (`6/5 loaded`) indicates that the virtual plugin `xcore` (registered in `KernelHandler`) is accounted for in `list_plugins()` but not in `n`. This is not a real performance bug, but a measurement bug.

---

### Plugin Calls

**sequential_call_ping**: mean=1.15ms, **errors=1000** — all requests failed. Looking at the code, `bench_sequential_calls` checks `r.get("status") != "ok"` but the `ping` plugin returns `{"status": "ok", "pong": True, ...}`. The likely cause is permission verification: `PermissionMiddleware` calls `engine.check(plugin_name, resource, action)` where `resource = kwargs.get("resource") or action`. Without `grant_all`, the plugin has no loaded policy → DENY. Latency measurements remain valid (the pipeline executes up to the deny), but the displayed throughput is misleading.

**sequential_call_echo_payload**: mean=1.41ms, 0 errors — consistent because permissions are apparently granted here (or the benchmark uses `grant_all` somewhere). The difference with ping is suspicious and warrants investigation.

**Concurrent calls**: errors at 10/50/100 levels confirm the same permission issue as ping. The average latency ~1.4-2ms under asyncio concurrency on a single plugin is reasonable. The throughput decreases from 709 to 481 ops/s as we scale from 10 to 100 concurrent clients, revealing **contention on the asyncio Lock** of the IPCChannel or the state machine.

**Routing**: mean=0.24ms, 0 errors — very good. Pure routing (dict lookup + dispatch) is O(1) and does not pass through the same permission layer as direct calls.

---

### Middleware

**Pipeline 0 middlewares**: mean=0.0034ms, 296k ops/s — excellent; compiling the pipeline into nested closures (`_compile_pipeline`) is highly efficient.

**Pipeline 4 middlewares**: mean=0.016ms, 61k ops/s — overhead of ~0.013ms per call for 4 noop middlewares. This is **4x** the baseline, i.e., ~3.25µs per middleware. Acceptable, but should be monitored in production with real middlewares (tracing, rate limiting, permissions).

---

### Events

**EventBus with no handler**: mean=6.6µs, 151k ops/s — the baseline cost of an empty dict lookup + creating an `Event` object at each call.

**1 handler**: mean=59µs, 17k ops/s — a **9x** spike for a single handler. The cost stems from `asyncio.gather` even for a single handler. Looking at the code, when `gather=True` (default), we systematically wrap in `asyncio.gather` even for n=1, creating an unnecessary asyncio task.

**10 handlers**: mean=178µs, 5.6k ops/s — near-linear growth, consistent.

**Wildcard**: mean=68µs — slightly slower than an exact handler (59µs); the overhead comes from iterating over `_wildcard_patterns` with regex matching. Regex pre-compilation is well implemented, but the O(N_wildcards) scan remains.

**HookManager 5 hooks**: mean=0.94ms, 1k ops/s — **16x** slower than the EventBus with 10 handlers for only 5 hooks. The reason lies in `_execute_single_hook`: for each synchronous hook, `asyncio.to_thread()` is called to submit to the thread pool executor, which is catastrophically expensive for trivial CPU-bound functions. The benchmark code registers `@hm.on` with sync functions, and HookManager systematically dispatches them via `asyncio.to_thread`.

---

### Permissions

**Cold**: mean=3.8µs, 262k ops/s — forcing `engine._cache.clear()` at each iteration is artificial but accurately measures the real cost of `PolicySet.evaluate()` with glob matching.

**Cached**: mean=2.0µs, 502k ops/s — **only 1.9x speedup**. The cache should be much faster. Looking at the code, `_cache` is a simple Python dict `(plugin, resource, action) → PolicyEffect`; the lookup should be sub-microsecond. The remaining overhead comes from `_audit()` being called even on cache hits, which performs `self._audit_log.append(entry)` + `events.emit_sync(...)` on every check.

---

### Cache

**cache_get_hot**: mean=1.57µs, 636k ops/s — excellent for a memory-based LRU backend.

**cache_set_single**: mean=3.8µs, 261k ops/s — slower than get due to calculating `expires_at` and LRU eviction.

**mset 100 keys**: mean=169µs, which is ~1.7µs/key — linear, correct.

**mget 100 keys**: mean=51µs, which is ~0.5µs/key — faster than mset, consistent.

---

### Tenancy

**Cache wrapper overhead**: set raw=2.5µs vs set wrapped=3.5µs (+40%), get raw=1.3µs vs get wrapped=4.5µs (+246%). The wrapped get is **3.4x slower** than the raw get. Looking at `TenantAwareCache.get()`, the issue is the try/except block around `cache.get()` to handle signature differences (with/without `default`), plus calling `_current_tenant_id.get()` (ContextVar lookup) and string concatenation for prefixing. Nothing severe in absolute terms (4.5µs), but the relative overhead is high.

**IPC Auth**: http_direct=0.22ms vs caller_allowed=2.15ms vs caller_denied=0.94ms. The HTTP fast-path (caller=None) is 10x faster than the IPC path. The difference between allowed (2.15ms) and denied (0.94ms) is surprising — the denied path should be faster since it short-circuits before calling `next_call`. The explanation is that `next_fn = AsyncMock(return_value={"status": "ok"})` — the asyncio mock on the allowed path adds significant overhead. These figures therefore do not reflect production reality.

**ipc_enforce_off_bypass**: mean=1.37ms, whereas one would expect it to be close to http_direct (0.22ms). The `enforce=False` bypass still calls `next_call`, which is a slow AsyncMock.

**wrap_services_per_call**: mean=7.9µs but median=4.9µs — high variance. Calling `wrap_services_for_tenant()` on every request creates new wrapper objects every time. In production, these wrappers are created once during the plugin's `_do_load()`, not on every dispatch — the benchmark thus measures a scenario that does not realistically occur.

---

### Capacity

The progression is erratic: 100 plugins in 4.7s (46ms/plugin), 500 plugins in **3.9s** (7.7ms/plugin), 1000 plugins in 29.8s (29.7ms/plugin). The dip at 500 is suspicious and likely a GC or filesystem cache artifact. `concurrent_calls_ok=0` across all levels confirms the permission bug identified above. Memory per plugin is virtually zero (0.014MB at 100, ~0 thereafter) because the Python module is shared — the benchmarked plugins are all identical and Python caches bytecodes.

---

### Priority Issues to Fix

**Critical bug (permissions)**: `sequential_call_ping` and all concurrent calls have 100% errors. In `PluginSupervisor.boot()`, `_load_permissions` is called via the `plugin.*.services_registered` event, but this handler is reactive and may trigger after calls in the benchmark. We should ensure `_load_permissions` is called synchronously after `load_all()`.

**HookManager via asyncio.to_thread**: replace the systematic call to `asyncio.to_thread` for trivial sync functions with a direct call, and reserve `asyncio.to_thread` exclusively for functions explicitly marked as blocking.

**EventBus single handler**: add a fast-path that avoids `asyncio.gather` when there is only one handler.

**Audit on permission cache hit**: move auditing after cache verification, or only log in debug mode.

**TenantAwareCache.get**: simplify the signature (choose one of the two interfaces), eliminate the hot try/except.

**Batch load measurement**: fix error calculation by excluding the virtual `xcore` plugin from the count.
