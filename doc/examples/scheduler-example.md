---
title: Advanced Scheduled Data Syncer
description: A background service coordinating Scheduler, XWorker, and External APIs.
icon: material/calendar-clock
---

# Advanced Scheduled Data Syncer

This example shows a **Trusted** plugin that synchronizes data from an external API into the local database on a schedule. It uses the `@cron` decorator from the SDK, delegates heavy processing to XWorker, and relies on the scheduler's built-in distributed lock for multi-worker safety.

---

### 1. The Manifest (`plugin.yaml`)

```yaml linenums="1"
name: "data_syncer"
version: "1.5.0"
execution_mode: "trusted"

permissions:
  - resource: "service:scheduler"
    actions: ["*"]
  - resource: "service:worker"
    actions: ["execute"]
  - resource: "db.sync_logs"
    actions: ["write"]
  - resource: "plugin:external_api"   # (1)!
    actions: ["execute"]
```

1.  Permission to call a dedicated gateway plugin that handles HTTP communication.

---

### 2. Implementation (`src/main.py`)

```python linenums="1"
import time
from xcore import TrustedBase, ok, error
from xcore.sdk import cron

class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.db = self.ctx.get_service("db")
        self.worker = self.ctx.get_service("worker")

    @cron("0 * * * *")   # every hour at :00
    async def trigger_sync(self) -> None:
        await self._orchestrate_sync()

    async def _orchestrate_sync(self) -> None:
        # The scheduler's distributed Redis lock already prevents concurrent
        # runs of trigger_sync across workers, so no extra lock is needed here.

        # 1. Fetch data via gateway plugin (IPC)
        response = await self.ctx.registry.get_service("gateway").call("fetch_raw_data")
        raw_items = response.get("data", [])

        # 2. Batch dispatch to workers
        for batch in self._chunks(raw_items, 100):
            self.worker.send("tasks.sync:process_batch", batch)

        # 3. Log result
        async with self.db.session() as sess:
            await sess.execute(
                "INSERT INTO sync_logs (timestamp, count) VALUES (:t, :c)",
                {"t": time.time(), "c": len(raw_items)},
            )

    def _chunks(self, lst: list, n: int):
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    async def handle(self, action, payload):
        if action == "force_sync":
            await self._orchestrate_sync()
            return ok(msg="Sync triggered manually")
        return error("Unknown action")
```

---

### 3. Key design points

#### No manual lock needed

Previous versions of this pattern used a cache key (`sync:active_lock`) as a manual distributed lock. This is no longer necessary: the `SchedulerService` automatically acquires a Redis lock (`xcore:sched:lock:data_syncer.trigger_sync`) before each execution and releases it when the job finishes. Workers that lose the race skip silently.

If the job exceeds the lock TTL (default 300 s), the lock expires and another worker can take over on the next trigger. For jobs that must never run concurrently regardless of duration, implement idempotency inside the job itself (e.g., a database-level unique constraint on the sync log).

#### Gateway pattern (IPC)

Instead of calling the external API directly, the plugin delegates to a `gateway` plugin. This separates network policy (retries, timeouts, credentials) from sync logic and keeps the plugin testable in isolation.

#### Background batching

Processing thousands of items in the main event loop would block requests. Chunking the data and forwarding batches to `XWorker` distributes the CPU load across physical worker processes.

---

### 4. Monitoring

```bash
# Check scheduled jobs
xcli services status --service scheduler

# Trigger a manual sync for testing
xcli plugin call data_syncer force_sync --payload '{}'

# Watch background worker logs
xcli worker start --queues default --loglevel debug
```

---

### See Also

[Scheduler Service](../services/scheduler.md)
:   Full reference for triggers, backends, scaling, and configuration.

[XWorker Internals](../services/xworker.md)
:   How task serialization and queues work.

[Plugin Registry](../advanced/registry.md)
:   How to discover and call gateway services via IPC.
