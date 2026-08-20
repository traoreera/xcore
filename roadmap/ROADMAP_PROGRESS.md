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

## 🔍 Technical Analysis (Update v2.3.5)

### Strengths
- **Advanced Runtime (V2)**: Support for ephemeral plugins with Warm Pool is a major technical achievement, enabling minimal "cold start" latency.
- **Security & Performance**: Recent optimizations on the EventBus and the permission engine have successfully reduced latency on the critical path.
- **Observability (V2)**: Real OpenTelemetry SDK + end-to-end W3C trace propagation (HTTP → plugin calls → sandbox IPC) now closes out V2's last two ⚠️ items.
- **Tenancy (V3)**: Resource isolation (DB/Cache) per tenant is mature and fully validated by integration tests.

### Known limitations to track during the V2 maintenance window
- **`self.tracer` / `self.metrics` / `self.health` are `None` inside ephemeral/sandboxed plugins** — no `PluginContext` is injected in `sandbox/worker.py`. Automatic supervisor-level tracing still covers those calls; only plugin-authored custom spans/metrics inside ephemeral code are affected. See `doc/observability/observability.md`.
- **Tiered cache has no cross-node invalidation push** — L1 staleness is bounded by `ttl`, not eliminated. Acceptable trade-off, documented in `doc/services/cache.md`.

### High-Priority Workstreams (V3, once the maintenance window ends)
1. **Clustering (V3)**: This is the missing technological leap. The framework must support inter-node communication (Cluster IPC).
2. **Resilience (V3)**: Implement Circuit Breaker and Failover patterns for inter-plugin stability.
