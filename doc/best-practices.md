---
title: Best Practices
description: Architectural patterns and design recommendations for building robust Xcore applications.
icon: material/thumb-up
---

# Best Practices

Building applications with Xcore requires a shift in mindset towards modularity, isolation, and security. Follow these best practices to ensure your ecosystem is scalable, maintainable, and secure.

---

### Architecture & Modularity

#### 1. Favor Composition over Inheritance
Avoid creating deep inheritance trees between plugins. Instead, expose capabilities via the `ServiceContainer` and use the `PluginRegistry` to discover and call other plugins.

#### 2. Keep Plugins Lean
Each plugin should have a single, well-defined responsibility. If a plugin starts growing too large, consider splitting it into a "Core" plugin (containing data models and base logic) and multiple "Extension" plugins.

#### 3. Use Dependency Waves
Group related plugins using the `requires:` block in `plugin.yaml`. This ensures a deterministic boot sequence and allows Xcore to load independent plugins in parallel.

---

### Security & Isolation

#### 1. Start with Sandboxing
Always develop new or third-party plugins in **Sandboxed Mode** first. Only move to **Trusted Mode** if the plugin requires native performance or access to restricted system resources that cannot be exposed via a service.

#### 2. Least Privilege Permissions
Be surgical with your `permissions:` declarations. Avoid `db.*` if you only need `db.users`. This minimizes the "blast radius" if a plugin is compromised.

#### 3. Mandatory Signing in Production
Always enable `strict_trusted: true` in your production environment. This prevents "shadow deployments" of unauthorized code and ensures that all trusted code has been audited and signed.

---

### Performance & Scalability

#### 1. Avoid Blocking the Event Loop
Xcore is built on `asyncio`. Any synchronous I/O or long-running CPU task in a Trusted plugin will freeze the entire application.
- Use `await` for all I/O.
- Use `run_in_executor` or the `XWorker` service for CPU-bound tasks.

#### 2. Cache Aggressively
Use the `CacheService` to store the results of expensive computations or frequent database queries. The `get_or_set` pattern is your best friend for maintaining a high-performance hot path.

#### 3. Use `emit_sync()` for Non-Critical Logic
For logging, analytics, or notifications, always use `self.ctx.events.emit_sync()`. This allows the main request to return to the user immediately while the background tasks are processed.

---

### Error Handling & Reliability

#### 1. Consistent Response Formats
Always use the `ok()` and `error()` helpers. This ensures that callers can handle responses predictably, regardless of which plugin they are calling.

#### 2. Implement Health Checks
Don't just rely on the framework. Implement custom `health_check()` logic in your plugins and services to detect functional degradation (e.g., an external API is down).

#### 3. Idempotent Background Tasks
Design your background tasks (via `Scheduler` or `XWorker`) to be idempotent. Assume that a task might be executed multiple times due to retries or network failures.

---

### Observability

#### 1. Label your Metrics
Always add labels (like `plugin`, `tenant_id`, or `action`) to your counters and histograms. This allows you to slice and dice your performance data in Prometheus/Grafana.

#### 2. Structured Logging
Never use `print()` or f-strings for logging. Use the structured logger:
`logger.info("Processed order", extra={"order_id": 123, "amount": 45.0})`

#### 3. Trace everything
Wrap complex logic blocks in manual spans:
`with self.ctx.tracer.span("heavy_calculation"): ...`
This makes it much easier to identify bottlenecks in distributed traces.
