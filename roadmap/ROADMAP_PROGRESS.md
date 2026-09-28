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

**Technical specification (2026-09-28)**: `roadmap/V3_NATIVE_RUNTIME_SPEC.md` — Python stays the control plane (plugins, SDK, API, orchestration); a new Rust native runtime (`xcore-runtime`, embedded via PyO3) owns cluster membership, inter-node transport, routing, the distributed side of XBus, circuit breaking, and failover. Every row below maps to a section of that spec — none of it is implemented yet, this is the target architecture for when the V2 maintenance window ends.

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
- **Sandbox hardening (v2.6.1/v2.6.2)**: 3 confirmed sandbox-escape techniques (`asyncio.create_subprocess_exec`/`_shell`, `__subclasses__()` walk to an already-loaded `subprocess.Popen`, dynamic `import posix`) found via dynamic testing and fixed by patching the dangerous objects directly rather than only gating imports by name — see `reports/sandbox_dynamic_security_analysis_2026-09-28.md`. Separately, an unspecified `execution_mode` in `plugin.yaml` now defaults to `sandboxed` instead of the `trusted`-equivalent `legacy` — fail-closed instead of fail-open. See `CHANGELOG.md` [2.6.1]/[2.6.2].

### Known limitations to track during the V2 maintenance window
- **`self.tracer` / `self.metrics` / `self.health` are `None` inside ephemeral/sandboxed plugins** — no `PluginContext` is injected in `sandbox/worker.py`. Automatic supervisor-level tracing still covers those calls; only plugin-authored custom spans/metrics inside ephemeral code are affected. See `doc/observability/observability.md`.
- **Tiered cache has no cross-node invalidation push** — L1 staleness is bounded by `ttl`, not eliminated. Acceptable trade-off, documented in `doc/services/cache.md`.
- **`ExecutionMode.LEGACY` is still functionally a pure alias of `TRUSTED`**, and can still be requested explicitly (`execution_mode: legacy` in `plugin.yaml`) — only the *implicit* default changed (v2.6.2), the enum value itself was not retired. `LagacyActivator` (note the typo) remains dead code, raising `NotImplementedError` unconditionally — harmless (never instantiated: `PluginLoader` maps `ExecutionMode.LEGACY` to `TrustedActivator()`) but worth deleting in a future cleanup pass.

### High-Priority Workstreams (V3, once the maintenance window ends)
1. **Clustering (V3)**: This is the missing technological leap. The framework must support inter-node communication (Cluster IPC).
2. **Resilience (V3)**: Implement Circuit Breaker and Failover patterns for inter-plugin stability.
