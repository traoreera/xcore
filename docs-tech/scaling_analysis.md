# XCore Architectural Scaling & Audit Report

## 1. Executive Summary
The XCore architecture is a robust "Modular Monolith" designed to manage dynamic plugins with strong isolation and dependency injection. While the current version (v2.0.0) successfully addresses several initial design flaws (e.g., namespace isolation), our audit identifies critical coupling points and anti-patterns that will hinder scalability and maintenance as the ecosystem grows.

This report outlines our findings and provides a concrete roadmap for future refactorings.

---

## 2. Layer Analysis & Audit

### Core Kernel (`xcore.kernel`)
- **Shared State Contention:** The framework relies on a shared `dict[str, Any]` for service discovery. This lacks encapsulation and is prone to race conditions during concurrent plugin operations.
- **Manual Orchestration:** `PluginSupervisor` manually configures permissions, rate limits, and routing. This approach is not extensible; adding new cross-cutting concerns (e.g., logging, circuit breakers) requires modifying the core.

### Plugins & Sandbox
- **Divergent Activation:** Trusted and Sandboxed plugins follow different activation paths, leading to code duplication in `PluginLoader`.
- **Fragile Isolation:** Trusted plugins use `sys.modules` manipulation for isolation, which can lead to memory leaks or stale state if sub-modules are not perfectly purged.

### Services Layer (`xcore.services`)
- **Open/Closed Violation:** Core service providers are hardcoded in the `ServiceContainer`. Adding a new core service requires a framework-level change.

---

## 3. Detected Anti-Patterns & Risks

| Anti-Pattern | Location | Impact | Risk Level |
| :--- | :--- | :--- | :--- |
| **Hardcoded Providers** | `container.py` | Violates Open/Closed Principle | Medium |
| **Manual Middleware Config**| `supervisor.py` | Hinders extensibility | High |
| **Cryptic Naming** | `lifecycle.py` | Increases cognitive load (`mems`) | Low (Fixed) |
| **Direct State Mutation** | `LifecycleManager` | Risk of inconsistent system state | High |

> **Note:** The cryptic `mems` method has been refactored to `propagate_services` as part of this audit to improve maintainability.

---

## 4. Proposed Refactorings & Improvements

### A. Unified & Scoped Service Registry
Merge `PluginRegistry` and `ServiceContainer` into a single, thread-safe registry that supports private vs. public scoping.

```python
from dataclasses import dataclass, field
from typing import Any, Dict
import threading

@dataclass
class ServiceEntry:
    obj: Any
    plugin: str
    scope: str = "public"  # "public", "private", or "protected"
    metadata: Dict[str, Any] = field(default_factory=dict)

class UnifiedServiceRegistry:
    def __init__(self):
        self._services: Dict[str, ServiceEntry] = {}
        self._lock = threading.Lock()

    def register(self, name: str, service: Any, plugin: str, scope: str = "public"):
        with self._lock:
            if name in self._services and self._services[name].scope == "protected":
                raise PermissionError(f"Cannot overwrite protected service: {name}")
            self._services[name] = ServiceEntry(obj=service, plugin=plugin, scope=scope)

    def get(self, name: str, requester: str = None) -> Any:
        entry = self._services.get(name)
        if not entry:
            raise KeyError(f"Service not found: {name}")

        if entry.scope == "private" and entry.plugin != requester:
            raise PermissionError(f"Access to private service '{name}' denied to '{requester}'")

        return entry.obj
```

### B. Event-Driven Lifecycle Hooks
Transition from manual orchestration to a reactive lifecycle using the `EventBus`. This decouples the core from individual plugin configurations.

```python
# In LifecycleManager.load()
async def load(self):
    await self._do_load()
    # Replace manual calls with events
    await self._events.emit("plugin.activated", {
        "name": self.manifest.name,
        "mode": self.manifest.execution_mode,
        "services": self._instance.get_exposed_services()
    })

# In PluginSupervisor (or a new PluginLifecycleObserver)
async def on_plugin_activated(self, event):
    # Reactive configuration of cross-cutting concerns
    name = event["name"]
    self._registry.register_all(name, event["services"])
    self._permissions.auto_load(name, self._loader.get(name).manifest)
    self._rate_limiter.auto_register(name, self._loader.get(name).manifest)
```

### C. Standardized IPC for Sandboxed Services
Expose services from sandboxed plugins via a standardized RPC-over-IPC protocol. This would allow the core to treat sandboxed services as "remote objects," unifying the API for developers regardless of the plugin's execution mode.

---

## 5. Final Recommendations
1. **Unify Service Discovery:** Implement the `UnifiedServiceRegistry` to centralize access control.
2. **Move to Reactive Lifecycle:** Use events to handle plugin startup and shutdown to improve extensibility.
3. **Enhance Sandbox Transparency:** Build a proxy layer so sandboxed services can be injected just like trusted ones.
