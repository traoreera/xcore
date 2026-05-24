---
title: Advanced Scheduled Data Syncer
description: A sophisticated background service coordinating Scheduler, XWorker, and External APIs.
icon: material/calendar-clock
---

# Advanced Scheduled Data Syncer

This example demonstrates a complex **Trusted** plugin designed to synchronize data from an external 3rd-party API into the local database and cache. It leverages the **Scheduler** for timing, the **XWorker** for offloading heavy processing, and **Hooks** for observability.

---

### 1. The Manifest (`plugin.yaml`)

We need a wide range of permissions to orchestrate this multi-step synchronization process.

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
  - resource: "cache.sync_locks"
    actions: ["*"]
  - resource: "plugin:external_api" # (1)!
    actions: ["execute"]
```

1.  Permission to call a dedicated "Gateway" plugin that handles HTTP communication.

---

### 2. Implementation (`src/main.py`)

This plugin uses the `on_start` hook to register a persistent job and the `on_stop` hook for clean state management.

```python linenums="1"
import time
from xcore import TrustedBase, ok, error
from xcore.services.base import ServiceStatus

class Plugin(TrustedBase):
    async def on_load(self):
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.scheduler = self.get_service("scheduler")
        self.worker = self.get_service("worker")

    async def on_start(self):
        # (1) Register a complex Cron Job
        # Runs every hour at minute 0
        @self.scheduler.cron("0 * * * *")
        async def trigger_sync():
            await self._orchestrate_sync()

    async def on_stop(self):
        # (2) Graceful state cleanup
        await self.cache.delete("sync:active_lock")
        print(f"[{self.name}] synchronization paused")

    async def _orchestrate_sync(self):
        # 1. Distributed Lock (to prevent parallel runs)
        if await self.cache.exists("sync:active_lock"):
            return

        await self.cache.set("sync:active_lock", True, ttl=300)

        try:
            # 2. Fetch Data via Gateway Plugin (IPC)
            response = await self.ctx.registry.get_service("gateway").call("fetch_raw_data")
            raw_items = response.get("data", [])

            # 3. Batch Dispatch to Workers
            # We don't process data here; we offload it to Celery.
            for batch in self._chunk_list(raw_items, 100):
                self.worker.send("tasks.sync:process_batch", batch)

            # 4. Log Success to Database
            async with self.db.session() as sess:
                await sess.execute(
                    "INSERT INTO sync_logs (timestamp, count) VALUES (:t, :c)",
                    {"t": time.time(), "c": len(raw_items)}
                )

        finally:
            await self.cache.delete("sync:active_lock")

    def _chunk_list(self, lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    async def handle(self, action, payload):
        if action == "force_sync":
            await self._orchestrate_sync()
            return ok(msg="Sync triggered manually")
        return error("Unknown action")
```

---

### 3. Orchestration Logic Explained

#### Distributed Locking
By using `self.cache` as a lock coordinator, we ensure that if synchronization takes longer than an hour, the next scheduled job won't start until the first one is finished. This is crucial for avoiding race conditions in data-intensive tasks.

#### Gateway Pattern (IPC)
Instead of importing `httpx` directly, this plugin calls a `gateway` plugin. This separates the **Network Policy** (retries, timeouts, credentials) from the **Sync Logic**.

#### Background Batching
Processing 10,000 items in the main event loop would block other requests. By chunking the data and sending it to `XWorker`, we distribute the CPU load across multiple physical worker processes.

---

### 4. Integration Monitoring

You can monitor the status of this background sync via the Xcore CLI.

```bash
# 1. Check if the job is scheduled
xcore services status --service scheduler

# 2. Trigger a manual sync for testing
xcore plugin call data_syncer force_sync --payload '{}'

# 3. Watch the background worker logs
xcore worker start --queues default --loglevel=debug
```

---

### See Also

[XWorker Internals](../services/xworker.md)
:   Understanding how task serialization and queues work.

[Plugin Registry](../advanced/registry.md)
:   How to discover and call "Gateway" services.

[Observability](../observability/observability.md)
:   Adding metrics to track sync duration and failure rates.
