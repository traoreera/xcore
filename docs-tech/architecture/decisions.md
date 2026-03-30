# Technical Decisions & Patterns

This document explains the "Why" behind the architectural choices in XCore. It is intended for developers who want to understand the framework's internal logic and design philosophy.

---

## 1. Modular Monolith vs. Microservices

**Decision**: XCore implements a Modular Monolith.

-   **Why?**: Microservices introduce significant overhead (network latency, distributed consistency, deployment complexity). A Modular Monolith allows for clean separation of concerns and independent plugin development while maintaining the performance and simplicity of a single binary.
-   **Pattern**: Separation by Plugins with shared Kernel Orchestration.

---

## 2. Strategy Pattern for Plugin Execution

**Decision**: Use the Strategy Pattern for `Trusted` vs. `Sandboxed` execution.

-   **Why?**: We needed a way to run plugins with different levels of trust without changing the core management logic.
-   **Implementation**:
    -   `BaseActivator`: The interface.
    -   `TrustedActivator`: In-process loading via `importlib`.
    -   `SandboxedActivator`: Out-of-process execution via `multiprocessing`.
-   **Benefit**: Easy to add future execution modes (e.g., WASM, Docker) by implementing a new strategy.

---

## 3. JSON-RPC 2.0 for IPC

**Decision**: Choose JSON-RPC 2.0 over OS Pipes for Sandbox communication.

-   **Why?**:
    -   **Standardization**: JSON-RPC is a well-known, simple protocol.
    -   **Compatibility**: It only requires basic string serialization, avoiding the security risks of `pickle` or the complexity of `gRPC`/`Protobuf`.
    -   **Performance**: For local OS pipes, the overhead of JSON serialization is negligible compared to the isolation benefits.

---

## 4. AST-Based Security Scanning

**Decision**: Perform static analysis on plugin code before execution.

-   **Why?**: Relying solely on OS-level isolation isn't enough for Python, where "monkey-patching" and introspection are common. The `ASTScanner` acts as a "firewall" for the Python runtime.
-   **Mechanism**: Blocks `Import` and `Attribute` nodes that match a forbidden list (e.g., `os`, `sys`, `__globals__`).
-   **Benefit**: Prevents sandbox escapes before they can even be attempted.

---

## 5. DAG-Based Dependency Resolution

**Decision**: Use Kahn's Algorithm for topological sorting of plugins.

-   **Why?**: Plugins often depend on services or events provided by other plugins. We need a deterministic load order to prevent "Service Not Found" errors during boot.
-   **Benefit**: Detects circular dependencies at boot time and ensures a stable, wave-based loading sequence.

---

## 6. Event Bus vs. Direct Calls

**Decision**: Use both.

-   **Direct Calls (`supervisor.call`)**: Used when a result is expected immediately (Request/Response). It passes through the security middleware.
-   **Event Bus (`ctx.events.emit`)**: Used for decoupled side effects (Pub/Sub). It allows multiple plugins to react to a single action (e.g., "User Created") without the caller knowing about the subscribers.

---

## 7. Configuration: YAML + Environment Variables

**Decision**: Use YAML for structure and `${VAR}` syntax for secrets.

-   **Why?**: YAML is human-readable and supports complex hierarchies. Environment variable injection ensures that secrets (like `DB_PASSWORD`) never end up in version-controlled configuration files.
-   **Pattern**: "Zero Config" defaults in Python dataclasses, overridden by YAML, overridden by Environment Variables.

---

## 8. Service Scoping & Protection

**Decision**: Prevent plugins from overwriting core kernel services.

-   **Why?**: To prevent malicious or buggy plugins from "hijacking" the database or cache service used by other plugins.
-   **Implementation**: A `PROTECTED_SERVICES` list in the `LifecycleManager` blocks registration of services with reserved names.
