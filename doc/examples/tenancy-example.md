---
title: Advanced Multi-Tenant Analytics
description: Building complex SaaS plugins with scheduled reports, event-driven data, and transparent isolation.
icon: material/account-group
---

# Advanced Multi-Tenant Analytics

This example demonstrates a sophisticated **Trusted** plugin for a multi-tenant SaaS application. It processes events from other plugins, stores them in tenant-isolated databases, and uses a **Scheduler** to generate per-tenant reports.

---

### 1. The Manifest (`plugin.yaml`)

This plugin acts as a central data hub, so it requires permissions to listen to events and manage its own schedule.

```yaml linenums="1"
name: "advanced_analytics"
version: "2.1.0"
execution_mode: "trusted"

permissions:
  - resource: "db.analytics_events"
    actions: ["*"]
  - resource: "cache.stats"
    actions: ["read", "write"]
  - resource: "service:scheduler"
    actions: ["*"]
  - resource: "events:user.*"    # (1)!
    actions: ["subscribe"]
```

1.  Permission to listen to all user-related events (e.g., `user.created` from the User Manager plugin).

---

### 2. The Implementation (`src/main.py`)

This implementation demonstrates how Xcore manages tenant context across asynchronous boundaries (Events and Scheduler).

```python linenums="1"
from xcore import TrustedBase, ok
from sqlalchemy import text, func, select
import logging

logger = logging.getLogger("xcore.analytics")

class Plugin(TrustedBase):
    async def on_load(self):
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.scheduler = self.get_service("scheduler")

    async def on_start(self):
        # (1) Event-Driven Data Collection
        @self.ctx.events.on("user.created")
        async def on_user_signup(event):
            # Xcore automatically propagates the tenant_id from the event emitter!
            await self._record_event("signup", event.data)

        # (2) Tenant-Aware Scheduling
        # This job will be executed for EVERY tenant currently active.
        @self.scheduler.cron("0 0 * * *")
        async def nightly_aggregation():
            await self._compute_daily_totals()

    async def _record_event(self, event_type: str, data: dict):
        async with self.db.session() as sess:
            # Query is automatically scoped to the correct tenant schema
            await sess.execute(
                text("INSERT INTO analytics_events (type, payload) VALUES (:t, :p)"),
                {"t": event_type, "p": str(data)}
            )

        # Cache increment is also tenant-prefixed (e.g., "acme:stats:signup")
        await self.cache.incr(f"stats:{event_type}")

    async def _compute_daily_totals(self):
        # Heavy aggregation logic...
        # The scheduler preserves the tenant context during execution.
        logger.info(f"Generating report for tenant: {self.ctx.tenant_id}")
        # ... aggregation logic ...

    async def handle(self, action, payload):
        if action == "get_dashboard":
            signups = await self.cache.get("stats:signup")
            return ok(dashboard={"signups": signups or 0})
        return ok()
```

---

### 3. Architecture Deep Dive

#### Automatic Context Propagation
One of Xcore's most powerful features is **asynchronous context propagation**.
- When the `User Manager` plugin emits `user.created`, it includes the current `tenant_id`.
- Xcore ensures that when this plugin's `@events.on` handler runs, `self.ctx.tenant_id` is correctly set to the emitter's tenant.
- This means your `self.db` and `self.cache` calls remain isolated without you passing IDs around manually.

#### Scheduler Isolation
Scheduled jobs are traditionally difficult to manage in multi-tenant systems. Xcore solves this by tracking which tenants have "active" plugins and spawning the job in the correct security context for each one.

---

### 4. Integration Monitoring

You can verify the isolation and scheduling via the CLI.

```bash
# 1. Check event subscription
xcore plugin info advanced_analytics

# 2. Inspect tenant-specific jobs
xcore services status --service scheduler --tenant acme_corp

# 3. View isolated logs
make logs-live | grep "analytics"
```

---

### See Also

[Multi-Tenancy Internals](../advanced/multi-tenancy.md)
:   Understanding how `tenant_id` is carried across async tasks.

[Event Bus Guide](../plugins/events-hooks.md)
:   Subscribing to system and plugin events.

[Database Schema Isolation](../services/database.md)
:   Setting up PostgreSQL schemas for this example.
