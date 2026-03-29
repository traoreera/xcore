# Technical Decisions & Patterns

This document details the software engineering patterns and architectural decisions that define XCore.

## 1. Minimal Core Philosophy
XCore is built on the principle that the kernel should only handle **orchestration**, **isolation**, and **communication**. All domain-specific logic is offloaded to plugins. This ensures that the core remains lightweight, highly stable, and easier to audit for security vulnerabilities.

## 2. Structural Patterns

### Strategy Pattern (Plugin Activators)
To handle different execution modes (`trusted` vs. `sandboxed`), XCore uses the **Strategy Pattern**.
- **The Interface**: `BaseActivator` defines how a plugin should be initialized.
- **Concrete Strategies**: `TrustedActivator` loads code into the current process memory, while `SandboxedActivator` spawns isolated processes.
- **Benefit**: Adding a new execution mode (e.g., WebAssembly or Docker-based) only requires a new strategy without changing the `PluginLoader` logic.

### Middleware Pattern (Supervisor Call Stack)
Cross-plugin communication follows the **Middleware Pattern** (similar to FastAPI or Express).
- **The Chain**: Each call passes through a series of "decorators" (Tracing -> RateLimiting -> Permissions -> Retry).
- **Benefit**: Concerns like logging, security, and resilience are decoupled from the core execution logic.

### Observer Pattern (Event Bus)
The `EventBus` implements an **Asynchronous Observer Pattern**.
- **Decoupling**: Plugins can emit events without knowing which other plugins are listening.
- **Scalability**: Handlers are executed concurrently via `asyncio.gather`, ensuring high throughput.

### Repository Pattern (SDK Data Access)
The SDK provides `BaseAsyncRepository` and `BaseSyncRepository` to encourage the **Repository Pattern**.
- **Abstraction**: Business logic interacts with "Repositories" instead of direct SQL queries.
- **Benefit**: Makes plugins database-agnostic and significantly easier to unit test with mocks.

### State Machine Pattern (Plugin Lifecycle)
The framework uses a **Finite State Machine (FSM)** to track plugin status (`UNLOADED`, `LOADING`, `READY`, `FAILED`).
- **Safety**: Prevents invalid operations, such as calling a plugin while it is still loading or has failed.
- **Auditability**: Every state transition can be logged or used to trigger health-recovery logic.

## 3. Communication Patterns

### JSON-RPC 2.0 (IPC)
For sandboxed plugins, we chose **JSON-RPC 2.0 over OS Pipes**.
- **Choice**: Compared to gRPC, JSON-RPC is simpler to implement in a cross-process Python environment and requires no complex code generation.
- **Security**: JSON-RPC over local pipes is inherently more secure than over a network socket as it prevents external sniffing or injection.

### Serialized Context Injection
Plugins do not receive direct references to kernel objects. Instead, they receive a **Context Object** (`self.ctx`) which provides a controlled API.
- **Why**: This prevents plugins from modifying the internal state of the kernel (monkey-patching).

## 4. Resource Management

### Sliding Window Rate Limiting
The rate limiter uses a **Sliding Window** algorithm stored in the `RateLimiterRegistry`.
- **Why**: This provides a smoother limit than fixed-window algorithms, preventing bursts at the edge of time boundaries.

### Topological Sorting (DAG)
XCore uses **Kahn's Algorithm** to sort plugins by their `requires` dependencies.
- **Why**: Ensures that if Plugin B depends on Plugin A, Plugin A is always fully loaded and its services registered before Plugin B starts.

## 5. Security Decisions

### Fail-Closed by Default
In the `PermissionEngine`, if a policy check fails or a manifest is corrupted, the system defaults to `DENY`.
- **Security**: It is better to break functionality than to allow unauthorized access during a configuration error.

### AST-based Forbidden Module Blocking
Instead of just blocking `import os`, XCore blocks any access to the `os` module, including via `getattr(pathlib, "os")` or `import importlib`.
- **Reasoning**: This prevents sophisticated sandbox escapes that attempt to re-import forbidden modules through transitive dependencies.
