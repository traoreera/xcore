# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.7.0] - 2026-10-01

### Changed
- **BREAKING (packaging): most backend-specific dependencies moved from hard requirements to opt-in extras.** A plain `pip install XCoreRuntime` no longer pulls in SQLAlchemy, database drivers, Redis, Celery, Alembic, the OTLP exporter, or `python-dotenv`. Each one was audited against actual usage in `xcore/` — `ServiceContainer`'s per-service providers (`xcore/services/container.py`) already import these lazily, only when the matching `services.*` config entry is present — and moved into a matching extra if it isn't needed for `import xcore` or the zero-config boot path:
  - `XCoreRuntime[postgres]` — SQLAlchemy (`[asyncio]`) + `psycopg2`, for `postgresql://` URLs in `services.databases`
  - `XCoreRuntime[sqlite]` — SQLAlchemy (`[asyncio]`) + `aiosqlite`, for `sqlite+aiosqlite://` URLs
  - `XCoreRuntime[db]` — both of the above combined
  - `XCoreRuntime[migrations]` — Alembic, only used by `MigrationRunner` (already imported on demand, with a clear `ImportError` message if missing)
  - `XCoreRuntime[redis]` — for `services.cache`/`services.scheduler` `backend: redis` or `tiered` (the default `memory` backend needs none of it)
  - `XCoreRuntime[worker]` — Celery, only instantiated when `services.xworker.enabled: true` (`False` by default)
  - `XCoreRuntime[tracing]` — the OTLP/HTTP exporter, only imported when `observability.tracing.endpoint` is set (console export, already in core, is the default)
  - `XCoreRuntime[dotenv]` — `.env` loading, already gracefully optional in the code (`try`/`except ImportError`)
  - `XCoreRuntime[metrics]` — `prometheus-client`, for `observability.metrics.backend: prometheus`. This closes a real gap: the package was imported by core runtime code (`kernel/observability/metrics.py`, `xcore/__init__.py`) but previously only listed under dev dependencies — a production install could never actually get it.
  - `XCoreRuntime[all]` — everything above, plus `sdk`/`xcli`/`cpp`

  **If you relied on a bare `pip install XCoreRuntime` for a working database, Redis cache/scheduler, Celery worker, migrations, OTLP export, `.env` loading, or Prometheus metrics, add the matching extra(s).** `apscheduler` stays in core: `SchedulerConfig.enabled` defaults to `True`, so the scheduler runs out of the box (in-memory backend) even with zero configuration — same for `opentelemetry-api`/`-sdk`, imported unconditionally at module load by `kernel/observability/tracing.py`.
- **Dependency versions refreshed**: `fastapi[standard]` 0.135→0.141, `pydantic` 2.11→2.13, `sqlalchemy` 2.0→2.1 (now pinned with `[asyncio]` in every DB extra — it was previously relying on `aiosqlite` to pull in `greenlet` transitively, which silently broke a Postgres-only install), `redis[hiredis]` upper bound raised 8→9, `apscheduler` →3.11.3, `opentelemetry-api`/`-sdk`/`-exporter-otlp-proto-http` 1.27→1.45, `alembic` →1.20, `python-dotenv` →1.2, `psycopg2` →2.9.13, `prometheus-client` 0.25→0.26 (dev dependency and new `metrics` extra aligned to the same constraint — `poetry lock` rejects mismatched ones for the same package). All backend extras are duplicated into `[tool.poetry.group.dev.dependencies]` so `poetry install --with dev` (what CI runs, without `--extras`) still exercises every backend in tests.

## [2.6.8] - 2026-10-01

### Fixed
- **A healthy sandboxed worker was killed after 10 cumulative CPU-seconds, then the plugin went `FAILED`**: `RLIMIT_CPU` counts the process's *total* CPU time since it started, but the worker set it once at startup (soft 10 s / hard 15 s, from a hardcoded `_SANDBOX_MAX_CPU_SEC=10`). The kernel's default `SIGXCPU` action terminates the process, and no handler exists (`signal` is forbidden to plugins) — so any plugin doing real work was killed after a few minutes of ordinary requests, restarted, killed again, and marked `FAILED` after `max_restarts` (3). Since `sandboxed` is the default execution mode (2.6.2), this hit every plugin that doesn't declare `execution_mode`. The limit is now two-level:
  - **soft limit = CPU budget per request** (`SandboxConfig.max_cpu_seconds`, default 10): the worker re-arms it to "CPU already consumed + budget" before every call (`_arm_cpu_budget`, `resource` is imported before the import guards go up). A request that burns more than its budget is still killed by `SIGXCPU`.
  - **hard limit = lifetime ceiling of a worker generation** (`SandboxConfig.max_cpu_lifetime_seconds`, default 3600, +5 s grace). A hard limit can never be raised without privilege, so it stays a kernel-enforced backstop a plugin cannot lift. Before reaching it the worker **recycles itself** between two requests (exit code `RECYCLE_EXIT_CODE`, 75) instead of being killed mid-request; `SandboxProcessManager` restarts it without counting a crash.
  Verified end-to-end with the real worker process: 8 requests of 0.5 s CPU each under a 1 s per-request budget all succeed (4 s cumulative — the old behavior killed the worker after the first couple); with a 4 s lifetime ceiling the worker exits with code 75 after 3 requests, not `-24` (`SIGXCPU`).
  **Behavior change to be aware of**: the kernel-enforced CPU backstop moves from 15 CPU-seconds per worker to 3600 per worker generation. Runaway requests are still bounded by the 10 s per-request soft limit and by the manager's wall-clock IPC timeout (`resources.timeout_seconds`, which kills and restarts a stuck worker); both settings are configurable.
- **A sandboxed plugin that crashed rarely still ended up `FAILED` for good**: `SandboxProcessManager._restarts` was only reset in `start()`, so three crashes spread over weeks exhausted `max_restarts`. If the subprocess ran at least `SandboxConfig.restart_reset_after` (60 s) before crashing, the restart sequence now starts over; a crash loop is still capped.

### Added
- **The event loop being frozen by synchronous plugin code is now visible and attributable.** A Trusted plugin runs on the application's single event-loop thread: CPU work, `time.sleep()` or a blocking call between two `await`s suspends every request, `asyncio.wait_for(timeout=...)` cannot interrupt it (measured: a `handle()` burning 1 s of CPU with `timeout_seconds: 0.2` returned `status: ok` after 1000 ms), and under the GIL threads do not help CPU-bound work. `LifecycleManager.call()` now times each synchronous *step* of `handle()` (`xcore.kernel.observability.blocking.watch_blocking`, transparent to results, exceptions, cancellation and timeouts) and logs `plugin blocked the event loop` with the plugin, the action and the blocked time when a step exceeds `plugins.loop_block_warn_ms` (default `250`, `0` disables; one warning per plugin per 10 s). `status()` gains `max_loop_block_ms`.
- Same detection for scheduler jobs (`scheduler job blocked the event loop` — a synchronous job runs entirely on the loop) and for synchronous hooks that exceed their `timeout` (`sync hook timed out, its worker thread keeps running`: `wait_for` stops waiting, not the thread).
- `SandboxConfig.max_cpu_seconds`, `max_cpu_lifetime_seconds`, `restart_reset_after`; `plugins.loop_block_warn_ms`.

### Documentation
- `doc/plugins/trusted-plugins.md`: why `timeout_seconds` cannot interrupt synchronous code and what the new warning means; a "Reload, Unload and Memory" section (`ctx.spawn_task` vs bare `asyncio.create_task`, what the kernel releases, `plugin instance still referenced after unload`, namespaced scheduler job ids); and the known limitation that **a reload only affects the server worker that handled the request** — there is no cross-worker reload broadcast yet.
- `CLAUDE.md`: version synced (it still said 2.5.3) and the plugin lifecycle/reload pitfalls fixed in 2.6.4–2.6.8 recorded.

### Not changed (deliberately)
- Synchronous scheduler jobs are **not** moved to `asyncio.to_thread` here: it would silently change the threading model for existing jobs (no running loop in the thread, non-thread-safe state). They are reported instead; moving them is a decision for a minor release.

## [2.6.7] - 2026-10-01

### Fixed
- **A plugin's HTTP routes were never removed on unload or reload — the old code kept serving**: `Xcore._unmount_plugin_router()` did `app.routes = [...]`, but `routes` is a read-only property in Starlette (`AttributeError: property 'routes' ... has no setter`, swallowed by the `EventBus` as an `event handler error`), and even with a working setter it filtered on `route.path`, an attribute FastAPI ≥ 0.14x's `_IncludedRouter` does not have. A reload therefore kept the previous router mounted (the old closures served requests and pinned the old plugin generation in memory) and `unload`/`disable` left a disabled plugin's endpoints reachable. Mounting now goes through a single `_mount_plugin_router()` that records the route objects `include_router()` added; unmounting removes exactly those (in place, invalidating FastAPI's route cache) plus any route whose `path` is the plugin prefix or below it. The prefix match is now segment-exact: unmounting `/plugins/shop` no longer removes `/plugins/shop2`. Boot and reload now share the same mount logic — the reload path used to always wrap the router in a second `/plugins/<name>` prefix while boot only did so when the router wasn't already prefixed — and the "plugin routes mounted" log no longer reads an undefined `wrapper` for a router that is already prefixed.
- **Unloading one instance of an Ephemeral plugin broke its sibling instances and unregistered the plugin**: every pooled instance of the same manifest shared one `sys.modules` namespace (`xcore_plugin_<name>`), and every instance's unload purged it and called `registry.unregister(<plugin>)`. Unloading or evicting one warm-pool instance made the others' lazy relative imports fail with `ModuleNotFoundError: No module named 'xcore_plugin_<name>'`, and removed the still-active plugin from the registry until the next instance happened to re-register it. Pooled instances (`LifecycleManager(..., pooled=True)`, used by `WarmPool` and `EphemeralHandler`) now get their own module namespace and leave the registry alone; `EphemeralHandler.stop()` unregisters the plugin once, when the plugin itself stops.
- **A plugin that exports a service could not be reloaded after boot**: `PluginSupervisor.boot()` step 5 registered the entire `ServiceContainer` as kernel-protected services — including the services plugins had just propagated into it — so the exporting plugin's next reload failed with `Impossible d'écraser le service protégé '<name>' (propriétaire actuel: kernel)`. Services already owned by a plugin in the registry (`PluginRegistry.service_owner()`) are now left with their owner.

### Added
- **Forced garbage collection after unload/reload, with a leak report**: a plugin instance lives in reference cycles (class, module, context, tasks), so reference counting never frees it and Python's automatic collector only reaches it after a full collection — measured on 3.14.7: a dead cycle promoted to the old generation was still alive after 11.5 million allocations on a 3-million-object heap (0 full collections ran), and the old generation of a reloaded plugin (module, state, buffers) stayed resident all that time. `LifecycleManager` now schedules one `gc.collect()` shortly after a persistent plugin is unloaded or reloaded (`_GC_DELAY_S`, 1 s; several unloads within the window share a single collection), then checks via a `weakref` that the old instance is gone. If it is not, it logs `plugin instance still referenced after unload` with the types of its referrers — the signature of a raw `asyncio.create_task`, a callback registered outside `ctx`, or a service held elsewhere. Ephemeral pool instances are exempt (short-lived young cycles; a full collection per call would cost more than it frees).
  A full collection is stop-the-world: ~15 ms on a 300 000-object heap, ~850 ms on 3 million. It happens once per unload/reload burst, never on the request path. Opt out with `plugins.gc_after_unload: false` in `integration.yaml` (default `true`).
- `PluginRegistry.service_owner(name)`; `LifecycleManager(..., pooled=...)`.
- Regression tests: `tests/unit/test_xcore_plugin_routes.py` (mount/unmount/remount against a real FastAPI app), `tests/unit/kernel/test_ephemeral_isolation.py`, `tests/unit/kernel/test_supervisor_exported_services.py` (real supervisor boot + reload), `tests/unit/kernel/test_plugin_release_watcher.py`.

## [2.6.6] - 2026-10-01

### Fixed
- **Unloading a plugin left its exported services callable in the shared container**: `PluginRegistry.unregister()` only cleans the registry, but `propagate_services()` also writes a plugin's exported services into the `ServiceContainer`'s shared dict — where they stayed after unload, reachable by every other plugin through `ctx.services` and pinning the dead plugin (instance, module, state) in memory. `LifecycleManager` now remembers what *it* wrote and removes exactly those entries at unload — never one that another plugin has since replaced.
- **A plugin's HTTP router and middlewares survived unload and reload**: `plugin_router`/`plugin_middlewares` were never reset in `_do_unload()`, so an unloaded handler kept the old router (and, through its closures, the old module), and a reload whose new code no longer exposed a router kept serving the previous one. `_collect_middlewares()` also *merged* the new `add_state()` result into the old dict (`.update`), so removed middlewares lived on. Both are now cleared at unload and replaced, not merged, on load.
- **Cancelled background tasks were not awaited before the plugin's module was dropped**: `_do_unload()` called `task.cancel()` and moved on, so the tasks' `finally` blocks ran *after* `sys.modules` had been purged. Tasks created with `ctx.spawn_task()` are now awaited after cancellation (bounded by `_TASK_CANCEL_TIMEOUT_S`, 2 s; a task that swallows `CancelledError` is logged and no longer blocks the unload). An unload triggered from inside one of those tasks no longer cancels itself.
- **`ctx.spawn_task()` leaked every finished task**: the tracking list only ever grew for the lifetime of the plugin. Finished tasks are now dropped as they complete, and a task that fails logs `spawned task failed` instead of surfacing as an unretrieved exception at garbage-collection time.

### Added
- `tests/unit/kernel/test_lifecycle_unload_cleanup.py`: router/middleware reset and replacement, exported-service removal (and respect for a service another plugin took over), cancelled-task cleanup ordering, tracking-list hygiene, unload from inside a spawned task.

## [2.6.5] - 2026-10-01

### Fixed
- **After boot, the scheduler's forced cleanup silently stopped working — and so did tenant isolation for `get_service()`**: `PluginContext.get_service()` consulted the `PluginRegistry` first. During `load_all()` the registry is still empty of core services, so it fell back to the plugin's own `ctx.services` — where the kernel had put the plugin's `_ScopedScheduler` tracker proxy (and the tenant-aware `db`/`cache` wrappers when tenancy is on). But once `supervisor.boot()` finished and ran `register_core_service()`, the registry started answering with the *raw* core objects. Any plugin loaded or reloaded after boot that did `self.get_service("scheduler").add_job(...)` therefore bypassed the tracker: the job stayed in `_JOB_REGISTRY` and APScheduler after unload, kept firing against a dead plugin, and pinned the unloaded instance, its module and its state in memory forever (verified: instance still alive after `gc.collect()`). The same bypass handed out the raw `db`/`cache` instead of `TenantAwareDB`/`TenantAwareCache`, so a plugin reloaded after boot escaped tenant isolation.
  `get_service()` now serves **kernel** services from the plugin's own context (new `PluginRegistry.is_core_service()` tells kernel services from plugin exports) and keeps resolving plugin-exported services — with their `public`/`private` scoping — through the registry.
- **Scheduler job ids collided across plugins**: `_JOB_REGISTRY` and APScheduler are global and keyed by the bare job id (`fn.__name__` by default), so two plugins that both register a `cleanup` job overwrote each other, and unloading one removed the other's job. `_ScopedScheduler` now namespaces ids as `<plugin>:<job_id>` for `add_job`, `cron` and `interval`; plugins keep using their own unprefixed ids (`remove_job`/`pause_job`/`resume_job` translate). Visible side effect: job ids shown by `scheduler.jobs()` and in the Redis job store are now prefixed with the plugin name.

### Added
- `PluginRegistry.is_core_service(name)`.
- `tests/unit/kernel/test_plugin_gc_scheduler.py`: job released and instance garbage-collectable after unload *after boot*, no job accumulation across reloads, no collision between plugins, `interval` decorator, tenant wrapping preserved by `get_service()` after boot.

## [2.6.4] - 2026-10-01

### Fixed
- **After boot, the second plugin reload/load of the whole process failed and left the plugin stuck in `FAILED`**: `LifecycleManager.propagate_services(is_reload=True)` ran `self._services.update(instance_services)`, but `self._services` *is* the `ServiceContainer`'s shared dict and `instance_services` is the plugin's `ctx.services` copy — which holds the plugin's own garbage-collection proxy (`_ScopedScheduler`) in place of the real scheduler (and tenant wrappers in place of `db`/`cache` when tenancy is on). The first reload therefore replaced the kernel's real `scheduler` in the shared container with that plugin's proxy; the next reload/load of *any* plugin then received a proxy-of-a-proxy, which the one-level `_real` unwrapping could not match against the kernel-protected service, raising `PermissionError: Impossible d'écraser le service protégé 'scheduler'`. The proxy chain also grew by one level per reload. Reproduced against a real `PluginRegistry` + `ServiceContainer` (the existing tests mocked the registry, so none of this was visible): `reload(A)` OK, then `reload(B)`, `load(C)` and `reload(A)` all failed.
  `LifecycleManager` now snapshots the services it injected (`_injected_services`, taken after tenant/GC wrapping, before `on_load`) and `propagate_services()` ignores any entry that is still *exactly* that injected object — it is received, not exported — in the registry loop, in the shared-container update and in the no-registry fallback check. Only services the plugin actually exported are written back; an attempt to replace a core service with a *different* object is still rejected. The proxy unwrapping fallback now strips every proxy level instead of one.
- **A plugin in `FAILED` could never be unloaded or reloaded**: the state machine only allowed `reset` from `FAILED`, and nothing in the kernel ever calls `reset` — so `_do_unload()` never ran for a plugin that failed mid-reload and its jobs, subscriptions, tasks and `sys.modules` entries stayed registered forever. `FAILED` now also accepts `unload` (forced cleanup) and `reload` (retry).
- **A failed `load()`/`reload()` left everything the plugin had already registered in place**: scheduler jobs, event/hook subscriptions, health checks, spawned tasks and `sys.modules` entries of a half-initialized plugin were never released. Both paths now run the forced cleanup (without calling the plugin's own hooks, whose state is inconsistent) before raising `LoadError`.

### Added
- `tests/unit/kernel/test_lifecycle_reload.py`: regression suite for reload/load *after* boot with a real registry and container (repeated reloads, cross-plugin reload, hot-load after a reload, exported services still propagated, core-service override still rejected, failed-load cleanup, unload/reload from `FAILED`).

## [2.6.3] - 2026-09-30

### Fixed
- **Sandboxed plugin logs never reached the console or `log/app.log`**: `xcore/kernel/sandbox/worker.py` hardcoded the subprocess `LOG_LEVEL` to `WARNING` when the env var wasn't set, and `SandboxProcessManager._spawn()` never set it — so a sandboxed plugin's `self.logger.info(...)` calls were dropped at the source regardless of `integration.yaml`'s `observability.logging.level`. Separately, `_watch_loop()` only ever read subprocess stderr once, in the crash path — so even `WARNING`/`ERROR`-level output from a healthy running plugin sat in the OS pipe buffer and was never drained during normal operation. Since `sandboxed` is now the default execution mode (2.6.2), this affected any plugin that doesn't explicitly declare `execution_mode`.
  Fixed by threading the real configured level through a new `KernelContext.log_level` field (set from `observability.logging.level` at boot) → `SandboxedActivator` → the subprocess `env` in `SandboxProcessManager._spawn()`, and by replacing the one-shot crash-time stderr read with a `_stderr_pump()` task that drains stderr continuously for the subprocess's whole lifetime and relays each line through the main process's logger (`xcore/kernel/sandbox/process_manager.py`).

## [2.6.2] - 2026-09-28

### Security
- **BREAKING: a plugin whose `plugin.yaml` omits `execution_mode` now defaults to `sandboxed` instead of `legacy`.** `legacy` is functionally a pure alias of `trusted` (`PluginLoader` registers the same `TrustedActivator()` for both) — meaning an unspecified plugin was silently getting full in-process trust (no AST scan restrictions, no filesystem guard, direct access to every service) rather than the safer, more restrictive default. Flagged in `reports/sandbox_dynamic_security_analysis_2026-09-28.md` / `roadmap/ROADMAP_PROGRESS.md` as a fail-open default worth a deliberate decision; the decision is fail-closed. Changed in `xcore/kernel/security/validation.py` (`ManifestValidator.load_and_validate`, the actual resolution path for a loaded plugin.yaml), `xcore/sdk/plugin_base.py` (`PluginManifest.execution_mode` dataclass default), and `xcore/sdk/manifest_schema.json` (schema default + adds the previously-missing `ephemeral` to the documented enum).
  **Migration**: any existing plugin relying on the implicit in-process default must now declare `execution_mode: trusted` (or `legacy`) explicitly in its `plugin.yaml`, or it will load as `sandboxed` and may fail on blocked imports/filesystem access it previously took for granted.
- `ExecutionMode.LEGACY` itself is unchanged and still resolves to `TrustedActivator()` when explicitly requested — only the *implicit* default moved.

## [2.6.1] - 2026-09-28

### Security
- **3 confirmed sandbox-escape techniques let a `sandboxed` plugin run arbitrary commands on the host**, found via dynamic testing (real plugins executed against a real `Xcore` instance, not static code review — see `reports/sandbox_dynamic_security_analysis_2026-09-28.md`):
  - `asyncio.create_subprocess_exec`/`_shell` — `asyncio` was on neither of the two forbidden-module lists.
  - `().__class__.__bases__[0].__subclasses__()` walking to an already-loaded `subprocess.Popen` — defeats both the static AST scan (no literal `__subclasses__`/`import subprocess` in source) and the runtime import guard (no `import` statement is ever executed; the class is already resident in memory before the guard installs).
  - Dynamic `import posix` — listed in the static scanner's `DEFAULT_FORBIDDEN` but missing from the runtime guard's `_FORBIDDEN_MODULES`; `posix` is the module `os` is built on and exposes near-equivalent primitives (`fork`, `execve`, ...).
  - Fixed in `xcore/kernel/sandbox/worker.py`: `pwd`/`grp`/`posix` added to `_FORBIDDEN_MODULES`, and a new guard layer patches the dangerous objects directly wherever they're reached from — `subprocess.Popen.__init__`, `subprocess.call`/`run`/`check_call`/`check_output`, the full `os.fork`/`os.exec*`/`os.spawn*`/`os.posix_spawn*`/`os.system`/`os.popen` family, and `asyncio.create_subprocess_exec`/`_shell` — rather than only gating imports by name. This closes the `__subclasses__()` bypass too, which a name-based fix alone cannot. Legitimate non-subprocess `asyncio` usage (`asyncio.sleep`, etc.) is unaffected — verified.
- Memory limits (`RLIMIT_DATA`/`RLIMIT_RSS`) and the filesystem guard (`allowed_paths`/`denied_paths`, directory traversal) were verified effective by the same dynamic testing — no change needed there.

## [2.6.0] - 2026-09-28

### Added
- **Persistent plugin enable/disable state** (`PluginStateStore`, `xcore/registry/state_store.py`): until now there was no way to disable a plugin short of deleting its folder — the manifest schema's `enabled` field lived under `runtime.health_check`, not on the plugin itself. `PluginLoader.load_all()` now consults a JSON file (`<plugins_dir>/../.xcore/plugins_state.json`) and skips disabled plugins at boot; `PluginSupervisor.enable()`/`disable(reason=...)` toggle the state live *and* persist it, so a process restart honors the same active/inactive set.
- **Forced garbage collection on unload/disable** (`PluginResourceTracker`, `xcore/kernel/runtime/plugin_gc.py`): `LifecycleManager._do_unload()` used to trust only the plugin's own `on_stop`/`on_unload` hooks plus `sys.modules` cleanup — no scheduler job, health check, or event/hook subscription was ever unregistered, and `PluginRegistry.unregister()` existed but was never called. The kernel now wraps scheduler/health/events/hooks at load time to track what a plugin registers, and forces their release on unload regardless of how well the plugin's own hooks behave. New `ctx.spawn_task()` for background tasks that are tracked and cancelled automatically.
- **HTTP routes unmounted on unload**: `xcore/__init__.py` only stripped a plugin's FastAPI routes from `app.routes` on reload — never on unload/disable, leaving a disabled plugin's endpoints reachable indefinitely. Extracted into `_unmount_plugin_router()`, now also subscribed to `plugin.*.unloaded`.
- **HTTP control center** on `/plugins/ipc/*`: `GET /registry` (the full plugin truth table — including disabled or never-loaded plugins, which `status()` never exposed), `POST /{name}/enable`, `POST /{name}/disable`.
- **IPC call supervision**: `PluginSupervisor.ipc_audit()`/`ipc_stats()` log every call (`plugin`, `action`, `caller`, `tenant_id`, status, duration) to a bounded audit trail, mirroring the existing `PermissionEngine.audit_log()` pattern. Exposed via `GET /plugins/ipc/audit`.
- **Event/hook supervision**: `EventBus.recent_emissions()`/`.stats()` and `HookManager.recent_emissions()` keep a record of recent emissions (event, handlers/hooks matched, errors, duration) — `EventBus` previously had no metrics at all. Exposed via `GET /plugins/ipc/events`.

### Fixed
- **`propagate_services()` broke reload/re-enable of a `TrustedBase` plugin**: `self._services` exposes the entire `ctx.services` dict for backward compatibility (including db/cache/scheduler), and `propagate_services()` tried to re-register those as the plugin's own exports. This passed on first boot (the registry doesn't protect core services until after `load_all()` runs), but any later reload raised `PermissionError: Impossible d'écraser le service protégé`. A collision on an object identical to the one already protected (received via injection, not exported) is now ignored; a genuinely different object (an actual override attempt) still raises.
- **Sandboxed subprocess wasn't recycled on IPC timeout**: `SandboxProcessManager.call()` only caught `IPCProcessDead`, not `IPCTimeoutError` — a subprocess that stopped responding without actually dying stayed unusable until the next periodic `_health_loop` check caught up with it. `call()` now recycles the subprocess immediately on either exception, on the failing request's own path, instead of waiting for the next health-check interval.
- **`PermissionEngine` audit log had no way to skip cache-hit entries**: every `allows()`/`check()` cache hit still appended to `_audit_log` unconditionally — the expensive part (event emission) was already skipped on cache hits, but the log append wasn't. New optional `PermissionEngine(audit_cache_hits=False)` skips it; default (`True`) keeps the existing behavior (complete audit trail) unchanged.
- **Stray temp directories from crashed test runs**: `tests/conftest.py`'s `plugins_dir`/`temp_dir` fixtures already clean up via `yield` + `shutil.rmtree`, but that teardown never runs if a test crashes hard (e.g. `SIGKILL`) before reaching it. `temp_dir` now uses the same distinguishing `xcore_test_` prefix as `plugins_dir`, and a new session-scoped autouse fixture sweeps any `xcore_test_*` directories left behind in the system temp dir at the end of the run — scoped to that exact prefix only, never a broader temp-dir sweep.

### Changed
- **Trimmed unused core dependencies**: `uvicorn` and `pydantic-settings` were never imported anywhere in `xcore` — both are already pulled in transitively by `fastapi[standard]` (confirmed against its own metadata) for anyone who needs them. `rich` had zero usage in the core package (it belongs to `xcorecli`, a separate install). `pydantic[email]` is now plain `pydantic` — `EmailStr`/`email-validator` were never used, and `fastapi[standard]` already brings in `email-validator` regardless. No behavior change; `poetry.lock` regenerated to match.

## [2.5.3] - 2026-09-09

### Fixed
- **`PluginLoader.shutdown()`**: `_stop_one` coroutine was defined but never awaited — `self._handlers.clear()` was called immediately, bypassing all plugin cleanup (`on_unload` hooks, resource release). Now uses `asyncio.gather` with timeout per handler before clearing.
- **`AutoDispatchMixin.handle()`**: Scanned `dir(self)` on every dispatch (O(N) per call). Added lazy `_build_action_map()` that pre-computes a `dict[action_name → method]` for O(1) dispatch.
- **`RoutedPlugin`**: Method named `RouterIn()` but `lifecycle.py` looks for `get_router()` — renamed to `get_router()` for consistency.
- **`PermissionEngine` cache**: Unbounded `dict` grew forever within process lifetime. Replaced with `OrderedDict`-based LRU cache (max 10,000 entries) with automatic eviction of oldest entries.
- **TenantAware wrappers** (`TenantAwareCache/DB/Scheduler`): `__getattr__` proxy hid API surface from IDEs and mypy. Added explicit method declarations for `mget`, `mset`, `disconnect`, `ping`, `stats` (Cache), `connect`, `disconnect`, `ping`, `status`, `engine` (DB), `start`, `shutdown`, `health_check`, `status` (Scheduler).
- **Version mismatch**: `__version__.py` was `2.3.3`, `pyproject.toml` was `2.5.2`, README badge was `v2.3.5`. Synced all to `2.5.2`.
- **Dead code**: Removed unused `__TenancyConfig` dataclass in `configurations/sections.py`.
- **`_is_db_adapter()`**: Fragile class-name-suffix detection replaced with `isinstance()` checks against actual adapter classes, with fallback for missing imports.
- **`RedisCacheBackend.clear()`**: Called `flushdb()` which deleted the entire Redis database (not just cache keys). Now uses `SCAN + DELETE` to only remove matching keys.
- **`TenantAwareDB._set_tenant_schema()`**: Used unquoted f-string in `SET search_path TO {tenant}, public`. Now quotes the identifier with double quotes (`"{tenant}"`) for PostgreSQL defense-in-depth against injection.

### Changed
- **Version synced to 2.5.3** across `__version__.py`, `pyproject.toml`, and README badge.

## [2.5.1] - 2026-08-20

### Fixed
- **`[cpp]`/`[all]` extras removed (urgent)**: `2.5.0` shipped `cpp = ["xscanner>=0.1.0"]`, but `xscanner` on PyPI is an unrelated third-party package — we never owned that name. `pip install XCoreRuntime[cpp]` would have silently installed a stranger's package instead of failing. Dropped both extras until the real accelerator package (`xcorescanner`) is published; `[sdk]` and `[xcli]` are unaffected.

## [2.5.0] - 2026-08-20

### Added
- **Optional extras** (`[project.optional-dependencies]`): `pip install XCoreRuntime[sdk]` (full plugin-author SDK, [`xcdk`](https://pypi.org/project/xcdk/)) and `pip install XCoreRuntime[xcli]` ([`xcorecli`](https://pypi.org/project/xcorecli/), the `xcli` command). `[cpp]`/`[all]` were part of this release but immediately broken — see `2.5.1`.

## [2.4.4] - 2026-08-20

First release actually published to PyPI as **`XCoreRuntime`** — `pip install XCoreRuntime` now works. `2.4.0`–`2.4.3` were cut while the release pipeline itself was still being fixed and never successfully reached PyPI (see `Fixed` below); no functional difference to document for those beyond what's already in `2.4.0`.

### Changed
- **PyPI distribution renamed to `XCoreRuntime`**: the registered PyPI project isn't `xcore` — `pyproject.toml`'s `name` didn't match, so the project-scoped `PYPI_TOKEN` was rejected with `403 Invalid API Token`. The **import name is unaffected**: `import xcore` still works, only `pip install <name>` changes.
- **`xcoresdk`/`xcoreCli` git dependencies dropped**: PyPI rejects any package whose metadata declares a direct VCS dependency (`xcoresdk @ git+https://...`). Removing them broke `import xcore` itself (`ModuleNotFoundError: No module named 'sdk'` — `xcore/kernel/security/section.py` and `validation.py` imported `PluginDependency` from the external `sdk` package unconditionally, not just as an SDK convenience). Fixed by vendoring the pre-extraction SDK source (`xcore/sdk/plugin_base.py`, `decorators.py`, `routers.py`, `mixin/ipc.py`, `adapter/*.py`) back locally: the kernel now depends on nothing external, and `xcore.sdk`'s newer features (`EventMixin`, `HookMixin`, `ObservabilityMixin`, `ScheduledMixin`, `cached`/`cron`/`interval`/`health_check`, `AutoMixin`, Mongo/Redis repositories) are picked up automatically if the `xcdk` package happens to be installed (`[sdk]` extra), and simply absent otherwise — no fake no-op fallbacks.
- **`xcore/kernel/security/{section,validation}.py`**: `PluginDependency` now imported from `...sdk.plugin_base` (local) instead of the external `sdk` package.

### Fixed
- **Release pipeline couldn't actually release**: `release.yml` only triggered on `push: tags:`, but the version-bump commit + tag pushed by `release-manual.yml` use the default `GITHUB_TOKEN` — GitHub deliberately never cascades a `push` event triggered by `GITHUB_TOKEN` into other workflow runs (anti-loop protection). `v2.3.5`(era) tags were pushed with no build/publish/release ever firing. `release.yml` now also accepts `workflow_dispatch` with a `tag` input, and `release-manual.yml` explicitly calls `gh workflow run release.yml -f tag=vX.Y.Z` after pushing the tag.
- **`pypa/gh-action-pypi-publish` token wiring**: the PyPI API token was passed via `env: PYPI_TOKEN`, which the action never reads (it only reads the `password:` input) — publish step silently no-op'd on auth. Fixed to `with: password: ${{ secrets.PYPI_TOKEN }}`.
- **`.github/workflows/labeler.yml`**: contained the label-mapping *config* (`"core": - changed-files: ...`) instead of a workflow definition — GitHub tried to parse it as a workflow and failed on every push. Moved the mapping to `.github/labeler.yml` (where `pr.yml`'s existing `🏷️ Auto Label` job already expected it) and deleted the broken duplicate workflow file.
- **`docs.yml`**: missing `permissions:` block meant the Netlify PR-preview comment step failed with `Resource not accessible by integration`. Added `contents: read` / `pull-requests: write`.
- **`xcore/kernel/security/validation.py`** isort ordering (introduced by the SDK-vendoring fix above).

### New tooling
- **`.github/workflows/release-manual.yml`**: `workflow_dispatch`-only release trigger — bump `pyproject.toml` (explicit version or `patch`/`minor`/`major`/pre-release), commit, tag, push, and dispatch `release.yml`. Supports `dry_run`.

## [2.4.0] - 2026-08-20

### Added
- **Real OpenTelemetry SDK integration and distributed trace propagation** (W3C `traceparent`, HTTP + sandbox IPC) — completes the tracing work started in `2.3.5`. See `doc/observability/observability.md`.
- **Tiered cache backend** follow-up work, and general V2 Industrialization roadmap close-out (PR #271).

## [2.3.5] - 2026-08-10

Closes out the V2 Industrialization roadmap: the two remaining ⚠️ items (Full OpenTelemetry, Distributed Tracing) are now implemented, and Advanced Hot Cache gets a tiered backend. V2 is now maintained in patch-release mode through December while running in production — see `ROADMAP_PROGRESS.md` for the V3 timeline decision.

### Added
- **Real OpenTelemetry SDK integration**: `Tracer`/`Span` (`xcore/kernel/observability/tracing.py`) now back onto a real `TracerProvider` when `observability.tracing.backend: opentelemetry` — console export (`SimpleSpanProcessor`, immediate) by default, OTLP/HTTP export (`BatchSpanProcessor`) when `endpoint` is set. Public API unchanged, fully backward compatible with the previous noop implementation.
- **Distributed trace propagation (W3C TraceContext)**: a single `trace_id` now survives across process boundaries. `TraceContextMiddleware` (new, `xcore/kernel/observability/http_middleware.py`) extracts the incoming `traceparent` HTTP header before any span opens; the sandbox IPC channel (`sandbox/ipc.py` / `sandbox/worker.py`) injects/parses `traceparent` across the hop to a sandboxed subprocess. New `inject_trace_context()` / `extract_trace_context()` helpers, and `span(..., context=...)` to parent a span explicitly.
- **`Tracer.shutdown()`**: flushes and stops the `TracerProvider`, wired into `Xcore.shutdown()`. Without it, spans still sitting in the `BatchSpanProcessor` buffer at process exit were silently dropped.
- **Tiered cache backend** (`backend: tiered` in `services.cache`): `TieredCacheBackend` (`xcore/services/cache/backends/tiered.py`) — memory L1 in front of Redis L2, read-through with backfill, write-through. No cross-node invalidation push (bounded by `ttl`) — documented trade-off, see `doc/services/cache.md`.
- New dependencies: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`.

### Changed
- **`ServerConfig.host` default**: `0.0.0.0` → `127.0.0.1`. Deployments that need to bind all interfaces (containers, LB in front) now do so explicitly via `app.server.host` in `integration.yaml` or `XCORE__APP__SERVER__HOST`.

### Fixed
- **Silent exception swallowing**: 3 bare `except: pass` blocks now log at debug level instead of discarding the error — `sandbox/ipc.py` (`IPCChannel.close`), `sandbox/worker.py` (`plugin.on_unload`), `tenancy/services.py` (`_set_tenant_schema` cleanup).
- **`sandbox/ipc.py`**: replaced `logging.getLogger()` with the project's `get_logger()`.

### Documentation
- `doc/observability/observability.md`: documented the real tracing backend, distributed propagation (HTTP + IPC), exporter selection table, and a new gotcha — `self.tracer`/`self.metrics`/`self.health` are `None` inside ephemeral/sandboxed plugins (no `PluginContext` injected there); automatic supervisor-level tracing still covers those calls without any plugin code.
- `doc/services/cache.md`: documented the `tiered` backend and its cross-node staleness trade-off.

## [2.3.4] - 2026-08-04

### Added
- **Ephemeral documentation**: New `doc/plugins/ephemeral-plugins.md` guide covering what Ephemeral mode is, when to use it, the warm pool lifecycle, configuration (per-plugin + global), plugin authoring, monitoring, and tuning advice. Registered in `mkdocs.yml`. Updated `execution-modes.md` (3-mode comparison table + Ephemeral section), `plugin-anatomy.md` (manifest reference), and `xcore-config.md` (`plugins.ephemeral` section).
- **CI/CD Netlify**: `docs.yml` now deploys MkDocs to Netlify instead of GitHub Pages. Production deploy on push `main` / tags / manual, deploy preview on PR. Requires `NETLIFY_AUTH_TOKEN` + `NETLIFY_SITE_ID` secrets. Build is now strict (`mkdocs build --strict`).

### Fixed
- **Doc links**: Fixed 6 broken relative links (`quickstart.md`, `advanced/multi-tenancy.md`, `sdk/examples/demo-plugin.md`) that made the strict MkDocs build fail.

### Fixed
- **Ephemeral per-plugin config**: `EphemeralActivator` now reads the `ephemeral:` block from `manifest.extra` when the manifest has no `ephemeral` attribute (the SDK's `PluginManifest` does not parse it as a field). Per-plugin config in `plugin.yaml` now works as documented, with global fallback preserved.
- **warm_pool.py**: Replaced `logging.getLogger()` with `get_logger()` from `xcore.kernel.observability` to comply with project logging conventions. Converted all 11 logger calls from `%s` stdlib style to structured kwargs logging.

### Documentation
- **ROADMAP_PROGRESS.md**: Updated V2 progress from 70% to 85% — Ephemeral mode and Warm Pool were already implemented but marked as not done. Corrected status for Hot Cache (now ⚠️). Added "Points d'Attention" section noting duplicate `kernel/middlewares/` directory.

## [2.3.3] - 2026-06-08

### Added
- **Mode Éphémère (Ephemeral Mode)**: Introduced a new execution mode for plugins that optimizes RAM usage on the host machine during hot reloads. This enables fully stateless plugins and reduces resource footprints.
- **Plugin Warm Pool**: Implemented a warm pool mechanism to accelerate plugin activation and lifecycle transitions.

### Changed
- **Event Bus Performance**: Optimized the `EventBus` for single-handler dispatch, reducing overhead for simple event flows.
- **Hot Reloading**: Optimized the hot reloading process to be more memory-efficient by leveraging ephemeral handlers.
- **Runtime Supervisor**: Updated the supervisor to manage ephemeral plugin instances and warm pools efficiently.
- **Internalization**: Updated RBAC error messages to English for better consistency.

### Fixed
- **Resource Management**: Addressed potential memory leaks during repeated hot reloads by implementing strict ephemeral lifecycle management.

## [2.3.2] - 2026-06-05

### Added
- **Python 3.12 Support**: Upgraded codebase and CI pipelines to support Python 3.12.
- **C++ Security Scanner**: Integrated high-performance `scanner_core` C++ extension for deeper security analysis.
- **Event Bus Singleton**: Implemented a global `EventBus` singleton available at configuration time, injected directly into middleware parameters.
- **Enhanced CI/CD**: Added comprehensive test coverage reporting and PR size validation to GitHub Actions.
- **CORS Configuration**: Centralized CORS configuration in `integration.yaml`.

### Changed
- **Modularization**: Decoupled core runtime from SDK and CLI.
    - `xcoreCli` is now an external dependency (`git+https://github.com/xcore-team/xcoreCli.git`).
    - `xcoresdk` is now an external dependency (`git+https://github.com/xcore-team/xcoreSDK.git`).
- **Internal Refactoring**:
    - Complete overhaul of the middleware pipeline for better performance and extensibility.
    - Improved database container connection handling with explicit session verification.
- **Documentation**: Migrated documentation system to MkDocs for better maintainability and rich search capabilities.

### Fixed
- **Plugin Sandbox**: Fixed a bug where environment variables were not correctly injected into the plugin context if missing from the manifest.
- **Database Reliability**: Resolved an issue where database connections could fail due to unverified sessions; added automatic verification before usage.
- **Plugin CLI**: Fixed various bugs in plugin-related CLI commands.

## [2.3.1] - 2026-05-29

### Fixed

- **database/session**: Connections were failing silently because the session was not verified before use. Added an explicit check on the session state (`is_active`) before each operation, with automatic reconnection if the session is expired or closed.
- **database/async_sql**: `pool_pre_ping=True` raised `ping() missing 1 required positional argument: 'reconnect'` when using the `aiomysql` driver. Pre-ping is now disabled automatically for `aiomysql` and `cymysql`, and is compensated by a pessimistic event listener (`engine_connect`) and `pool_recycle`.
- **database/async_sql**: Improved handling of dead connections — `OperationalError` and `DisconnectionError` errors during rollback are now caught and logged instead of crashing the worker.
- **database/_utils**: The `read_timeout` and `write_timeout` parameters are exclusive to `pymysql`. `sanitize_connect_args()` now filters them out for `aiomysql` with an explicit warning, avoiding a silent connection error.
- **database/migrations**: `MigrationRunner._is_async()` did not recognize the `+aiomysql` and `+asyncmy` suffixes, forcing the synchronous path on async connections. Both drivers are now included in `async_markers`.
- **database/container**: The `DatabaseConfig` configuration did not expose certain production parameters (`pool_timeout`, `pool_reset_on_return`, `connect_args`, `isolation_level`, `execution_options`). These fields are now read from `integration.yaml` and passed to the adapters.

### Improved

- **CI/CD**: Updated `ci.yml` workflow — refined the coverage step, reviewed PR labels, and added the `pr.yml` workflow to validate PR titles (conventional commits) and PR sizes.
- **CI/CD**: `security.yml` workflow — restricted Bandit scans to existing folders (`xcore/`, `tests/`) to eliminate false positives on `extensions/` and `plugins/`.
- **Tests**: Fixed `test_tenancy.py` test — aligned assertion with actual `ContextVar` behavior after reset.
- **Documentation**: Complete overhaul of the CLI section (`doc/cli/`) with detailed guides for installation, configuration, and the `worker`, `plugin`, `sandbox`, `manager`, and `migration` commands. Added the SDK API reference (`doc/sdk/api/`).
- **Observability**: Enriched `XcoreLogger` with structural support for contextual fields; extended `MetricsCollector` with documented `memory` and `prometheus` backends.

## [2.3.0] - 2026-05-14

### Added
- **Multi-tenancy Native (Axe 1)**:
    - `TenantMiddleware`: Extracts `tenant_id` from HTTP header (`X-Tenant-ID`) or subdomain; injects `request.state.tenant_id`.
    - `TenantAwareCache`: Wraps cache and automatically prefixes all keys with `{tenant_id}:`.
    - `TenantAwareDB`: Wraps SQL adapters and executes `SET search_path TO {tenant_id}, public` (PostgreSQL) before each query.
    - `TenantAwareScheduler`: Prefixes APScheduler `job_id` with `{tenant_id}:`.
    - `wrap_services_for_tenant()`: Replaces services in plugin context at each call; zero code changes for existing plugins.
- **IPC Authorization (allowed_callers)**:
    - `IPCAuthMiddleware`: First middleware in the pipeline; checks `allowed_callers` declared in `plugin.yaml`.
    - **Deny-by-default**: IPC calls are denied if the list is empty or missing. Direct HTTP calls (caller=None) still pass.
    - `PluginLoader.get_manifest(name)`: Added method to retrieve manifest from middleware.
- **@schema Decorator (Axe 3)**:
    - Versioned decorator with built-in validation (Pydantic).
    - `SchemaRegistry`: Singleton storing all schemas declared via `@schema`.
    - `BreakingChangeDetector`: Detects breaking changes between two registry versions.
    - CLI: `xcore plugin validate --check-breaking schemas_v1.json`.
- **Configuration**:
    - `tenancy:` section in `integration.yaml` with 8 flags: `enabled`, `header`, `subdomain`, `default_tenant`, `isolate_cache`, `isolate_db`, `isolate_scheduler`, `enforce_ipc`.
    - `TenancyConfig` dataclass in `configurations/sections.py`.
    - `allowed_callers: list[str]` added to `PluginManifest`.
- **Testing**:
    - 58 new tests: `tests/unit/kernel/test_tenancy.py` (41) and `tests/integration/test_tenancy_integration.py` (17).
- **Documentation**:
    - `doc/guides/tenancy.md`: Complete multi-tenant guide.
    - `doc/guides/plugin-manifest.md`: `plugin.yaml` reference.
    - `doc/reference/configuration.md`: Documented `tenancy:` section.
    - `doc/reference/sdk.md`: Documented `@schema`.
    - `doc/guides/security.md`: IPC and `allowed_callers` section.
    - `doc/architecture/decisions.md`: Decisions 7 (location), 8 (IPC deny-by-default), 9 (@schema source of truth).

## [2.2.1] - 2026-05-24

### Fixed
- **database/async_sql**: `pool_pre_ping=True` caused `ping() missing 1 required positional argument: 'reconnect'` with aiomysql. Pre-ping is now disabled automatically for aiomysql/cymysql and compensated by a pessimistic event listener + `pool_recycle`.
- **database/migrations**: `MigrationRunner._is_async()` did not recognize `+aiomysql` and `+asyncmy` drivers, forcing synchronous path on async connections.
- **database/_utils**: `read_timeout` and `write_timeout` are pymysql-only parameters. `sanitize_connect_args` now filters them for aiomysql with an explicit warning.

## [2.2.0] - 2026-05-24

### Added
- **DatabaseConfig**: New configurable pool parameters in `xcore.yaml`: `pool_pre_ping`, `pool_recycle`, `pool_timeout`, `pool_reset_on_return`, `connect_args`, `isolation_level`, `execution_options`.
- **database/adapters/_utils.py**: New module for driver detection and connection argument sanitization.

### Fixed
- **database/async_sql**: Fixed stale connections (MySQL/MariaDB) after `wait_timeout`.
- **database/async_sql**: Added missing `@asynccontextmanager` on `session()`.
- **database/async_sql + sql**: Added missing `disconnect()`.
- **database/async_sql + sql**: Improved error handling during rollback on dead connections.

## [2.2.0] - 2026-05-14

### Changed
- **Security**: Removed `python-jose` and `python-ecdsa` to eliminate vulnerability to Minerva timing attacks (CVE-2024-23342).
- **Cleanup**: Removed 7 unused dependencies (`pillow`, `watchdog`, `user-agents`, `aiocache`, `toml`, `mysql-connector-python`).
- **Optimization**: Moved `psutil` to dev dependencies and `markdown` to docs dependencies.

## [2.1.3] - 2026-05-13

### Added
- **XWorker (Native Celery)**: Full Celery integration in `ServiceContainer`.
- **CLI xcore worker**: Command to manage FastAPI and Celery processes (`start`, `stop`, `status`, `logs`, etc.).
- **Extended Configuration**: FastAPI constructor parameters and uvicorn parameters configurable via YAML.
- **Declarative Middleware System**: Automatic loading from `integration.yaml`.

## [2.1.2] - 2026-04-29

### Fixed
- 13 critical test failures resolved (kernel, permissions, sandbox).
- AST Scanner: detection of bypasses via import aliases.

### Improved
- **Performance**:
    - LRU Cache on `PermissionEngine`: +34% throughput.
    - Native `mset`/`mget` on Redis: up to 77x faster on batch operations.
    - Pre-compiled regex in `Policy.matches()`: short-circuit in 0.4 µs.
- **Quality**:
    - `pytest-benchmark` integration.
    - Pre-commit hooks for black, isort, and flake8.
    - `pyproject.toml` migrated to PEP 621.

## [2.0.0] - 2026-04-15

### Added
- **Plugin-First Architecture**: Modular kernel, separation of Kernel / Services / Plugins.
- **Advanced Sandboxing**: OS subprocess isolation, JSON-RPC 2.0 communication.
- **ServiceContainer**: Dependency injection for DB (SQLAlchemy 2.0), Cache (Redis/Memory), Scheduler (APScheduler).
- **MiddlewarePipeline**: Pre-compiled pipeline (Tracing → RateLimit → Permissions → Retry).
- **SDK**: `@action`, `@router`, `@validate_payload`, `AutoDispatchMixin`, `RoutedPlugin`.
- **RBAC**: Pluggable `AuthBackend` + declarative `RBACChecker`.
- **StateMachine**: FSM per plugin with validated transitions.
- **PluginRegistry**: Metadata, dependencies, semver versioning.

## [1.x] - Legacy

### Added
- Initial stable release based on FastAPI.
- Monolithic plugin system without isolation.
- Limited support for asynchronous services.
