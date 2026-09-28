# 🗺️ XCore Roadmap Progress

This document outlines the current state of the XCore framework relative to the goals defined in the V1 to V5 roadmap.

## 📊 Global Summary

| Version | Focus | State | Progress |
| :--- | :--- | :--- | :--- |
| **V1** | Kernel Foundation | **Completed** | 100% |
| **V2** | Industrialization | **Completed** | 100% |
| **V3** | Distribution | **Started** | 25% |
| **V4** | Cloud Native | **Conceptual** | 5% |
| **V5** | AI Native Intelligence | **Conceptual** | 0% |

---

## 🚀 V1 — Kernel Foundation
**Goal: Build a solid plugin-first framework.**

| Feature | State | Location / Note |
| :--- | :---: | :--- |
| Plugin Loader | ✅ | `xcore/kernel/runtime/loader.py` |
| Lifecycle Manager | ✅ | `xcore/kernel/runtime/lifecycle.py` |
| Service Container (DI) | ✅ | `xcore/services/container.py` |
| Plugin Manifest (`plugin.yaml`) | ✅ | `xcore/kernel/security/validation.py` |
| Trusted Plugins | ✅ | `xcore/kernel/runtime/activator.py` |
| Sandbox Plugins | ✅ | `xcore/kernel/sandbox/` |
| Internal IPC | ✅ | `xcore/kernel/sandbox/ipc.py` |
| Event Bus (XBus) | ✅ | `xcore/kernel/events/bus.py` |
| Centralized Configuration | ✅ | `xcore/configurations/` |
| System Permissions | ✅ | `xcore/kernel/permissions/` |
| Hooks & Middleware | ✅ | `xcore/kernel/runtime/middlewares/` |
| AST Security Scanner | ✅ | `xcore/kernel/security/validation.py` |

---

## ⚡ V2 — Industrialization
**Goal: Harden the runtime and prepare for distributed architectures.**

| Feature | State | Location / Note |
| :--- | :---: | :--- |
| ExecutionMode.EPHEMERAL | ✅ | `xcore/kernel/runtime/ephemeral_handler.py` |
| Warm Pool Plugins | ✅ | `xcore/kernel/runtime/warm_pool.py` |
| Schema Registry | ✅ | `xcore/kernel/schema/registry.py` |
| Automatic Contract Validation | ✅ | `xcore/kernel/schema/checker.py` |
| Full OpenTelemetry | ✅ | Real `TracerProvider` (console/OTLP-HTTP) — `xcore/kernel/observability/tracing.py` |
| Distributed Tracing | ✅ | W3C traceparent propagated across HTTP entry + sandbox IPC — `http_middleware.py`, `sandbox/ipc.py` |
| Prometheus Metrics | ✅ | `xcore/kernel/observability/metrics.py` |
| Private Plugin Registry | ✅ | `xcore/registry/index.py` |
| Advanced Hot Cache | ✅ | Tiered backend (memory L1 + Redis L2) — `xcore/services/cache/backends/tiered.py` |
| Loader Optimizations | ✅ | Topological sort by waves implemented |

**V2 maintenance window**: V2 is held at feature-complete and run in production through **December 2026** before starting V3 — each issue found in production gets patched into a V2.3.x release rather than folded into V3 work. See `CHANGELOG.md` for the patch history.

---

## 🌐 V3 — Distribution
**Goal: Scale out beyond a single process.**

| Feature | State | Location / Note |
| :--- | :---: | :--- |
| Static Federation | ❌ | Not implemented |
| FederatedHandler | ❌ | Not implemented |
| Inter-node Routing | ❌ | Not implemented |
| Cluster IPC | ❌ | Not implemented |
| Distributed Event Bus | ❌ | Not implemented |
| Comprehensive Multi-tenancy | ✅ | `xcore/kernel/tenancy/` (DB/Cache/Scheduler Wrappers) |
| AgentBase IA | ❌ | Not implemented |
| Hot Reload Plugins | ✅ | Functional via `PluginLoader.reload` |
| Service Hot-Swap | ✅ | Partially supported via reload and dynamic Registry |
| Circuit Breaker | ❌ | Not implemented |
| Failover | ❌ | Not implemented |

---

## ☁️ V4 — Cloud Native Platform
**Goal: Transform XCore into a full platform.**

| Feature | State | Location / Note |
| :--- | :---: | :--- |
| Public Marketplace | ⚠️ | Basic client present (`xcore/marketplace/`) |
| Cluster Manager | ❌ | Planned |
| Auto-scaling | ❌ | Planned |
| Plugin Store | ❌ | Planned |
| XCore Hub | ❌ | Planned |

---

## 🤖 V5 — AI Native Intelligence
**Goal: Make XCore an AI-native platform.**

| Feature | State | Location / Note |
| :--- | :---: | :--- |
| Integrated Kernel XMind | ❌ | Conceptual |
| Distributed Agents | ❌ | Conceptual |
| Native MCP | ❌ | Conceptual |
| AI Service Discovery | ❌ | Conceptual |

---

## 🔍 Technical Analysis (Update v2.7.0)

### Strengths
- **Advanced Runtime (V2)**: Support for ephemeral plugins with Warm Pool is a major technical achievement, enabling minimal "cold start" latency.
- **Security & Performance**: Recent optimizations on the EventBus and the permission engine have successfully reduced latency on the critical path.
- **Observability (V2)**: Real OpenTelemetry SDK + end-to-end W3C trace propagation (HTTP → plugin calls → sandbox IPC) now closes out V2's last two ⚠️ items.
- **Tenancy (V3)**: Resource isolation (DB/Cache) per tenant is mature and fully validated by integration tests.
- **Plugin lifecycle hardening (V2, v2.6.0)**: persistent enable/disable state (`PluginStateStore`) that survives restarts, forced resource cleanup on unload (scheduler jobs, health checks, event/hook subscriptions, exported services — previously leaked silently), and an HTTP control surface (`/plugins/ipc/registry|enable|disable|audit|events`) with an IPC-call and event/hook audit trail. See `CHANGELOG.md` [2.6.0].
- **Dependency hygiene (v2.7.0)**: core `dependencies` reduced to what `import xcore` and the zero-config boot path actually need; backend-specific packages (DB drivers, Redis, Celery, Alembic, OTLP exporter) moved to opt-in extras, closing a gap where `prometheus-client` was imported by core runtime code but only ever available via dev dependencies. See `CHANGELOG.md` [2.7.0].

### Known limitations to track during the V2 maintenance window
- **`self.tracer` / `self.metrics` / `self.health` are `None` inside ephemeral/sandboxed plugins** — no `PluginContext` is injected in `sandbox/worker.py`. Automatic supervisor-level tracing still covers those calls; only plugin-authored custom spans/metrics inside ephemeral code are affected. See `doc/observability/observability.md`.
- **Tiered cache has no cross-node invalidation push** — L1 staleness is bounded by `ttl`, not eliminated. Acceptable trade-off, documented in `doc/services/cache.md`.
- **Sandbox escape confirmed via dynamic testing (2026-09-28)**: 3 working techniques let a `sandboxed` plugin run arbitrary commands on the host — `asyncio.create_subprocess_exec`/`_shell` (module never on any forbidden-module list), `().__class__.__bases__[0].__subclasses__()` walking to an already-loaded `subprocess.Popen` (defeats both the static AST scan and the runtime import guard, since no `import` statement is ever executed), and dynamic `import posix` (listed in the static scanner's forbidden set but missing from the runtime guard's — `posix` gives near-`os`-equivalent access). Memory limits (`RLIMIT_DATA`/`RLIMIT_RSS`) and the filesystem guard were verified effective by the same testing. See `reports/sandbox_dynamic_security_analysis_2026-09-28.md` for full detail and proposed fixes (none applied yet — pending a decision on scope).
- **`ExecutionMode.LEGACY` relevance**: functionally a pure alias of `TRUSTED` (`PluginLoader` registers the same `TrustedActivator()` for both), yet it is `PluginManifest.execution_mode`'s **default value** when a `plugin.yaml` omits the field — meaning an unspecified plugin silently gets full in-process trust rather than defaulting to the safer `sandboxed`. `LagacyActivator` (note the typo) exists but is dead code, raising `NotImplementedError` unconditionally. Recommendation: either retire `LEGACY` (rename references to `TRUSTED`, drop the dead activator) or keep it strictly as a documented historical alias with a startup warning nudging authors toward an explicit mode — but the current silent-default-to-full-trust behavior is worth a deliberate decision either way, not something to leave unexamined.

### High-Priority Workstreams (V3, once the maintenance window ends)
1. **Clustering (V3)**: This is the missing technological leap. The framework must support inter-node communication (Cluster IPC).
2. **Resilience (V3)**: Implement Circuit Breaker and Failover patterns for inter-plugin stability.
3. **Sandbox hardening (carried over from V2 maintenance)**: apply the fixes from `reports/sandbox_dynamic_security_analysis_2026-09-28.md` — syncing the two forbidden-module lists is trivial, patching `subprocess.Popen.__init__`/`os.fork`/`os.execve` directly (rather than only gating imports) is the more robust fix that survives future variants of the same bypass class.
