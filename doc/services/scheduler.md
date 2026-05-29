---
title: Scheduler Service
description: Background task scheduling for Xcore using APScheduler.
icon: material/calendar-clock
---

# Scheduler Service

The `SchedulerService` allows you to schedule asynchronous background tasks directly within your Xcore application. It is built on top of [APScheduler](https://apscheduler.readthedocs.io/) and supports interval-based, date-based (one-shot), and cron triggers.

---

### Prerequisites

- [x] [Service Container](./services.md) overview understood
- [x] `apscheduler` package installed (`pip install apscheduler`)
- [ ] `redis` driver (only if using the Redis job store)

---

### Architecture

#### Dispatch pattern

All jobs — including bound methods from plugins — are stored through a two-level indirection:

```
APScheduler (Redis)
  └─ stores: "xcore.services.scheduler.service:_dispatch_job"  +  args=["job_id"]
       └─ at runtime → looks up _JOB_REGISTRY["job_id"] → calls real callable
```

This means Redis never needs to serialize the actual callable. Bound methods, closures, and objects with database connections are all supported without pickling issues.

#### Distributed lock (multi-worker)

When `backend: redis`, each job execution is guarded by a Redis lock (`xcore:sched:lock:<job_id>`).
If several workers receive the same trigger simultaneously, only the first one executes — the others skip silently.

```
Worker 1  ──┐
Worker 2  ──┼──→  trigger fires  ──→  SET xcore:sched:lock:my_job NX EX 300
Worker 3  ──┘                             ├─ Worker 1 → OK  → executes
                                          ├─ Worker 2 → nil → skip
                                          └─ Worker 3 → nil → skip
```

---

### Practical Guide

#### 1. SDK decorators (recommended)

Use `@cron` and `@interval` from `xcore.sdk` in any plugin that inherits `ScheduledMixin` (included automatically via `AutoMixin`).

```python linenums="1"
from xcore.sdk import cron, interval

class Plugin(TrustedBase):

    @cron("0 3 * * *")          # daily at 03:00
    async def nightly_cleanup(self) -> None:
        ...

    @interval(minutes=5)
    async def heartbeat(self) -> None:
        ...
```

Jobs are registered on `on_load` and removed on `on_unload` — no manual lifecycle management needed.

#### 2. Direct API

```python linenums="1"
scheduler = self.ctx.get_service("scheduler")

scheduler.add_job(
    self.send_reminder,
    trigger="date",
    run_date=payload["time"],
    job_id=f"reminder_{payload['id']}",
)
```

#### 3. One-shot date job

```python linenums="1"
from datetime import datetime, timedelta

scheduler.add_job(
    notify_user,
    trigger="date",
    run_date=datetime.now() + timedelta(hours=2),
    job_id="notify_123",
)
```

---

### API Reference

| Method | Return | Description |
|--------|--------|-------------|
| `add_job(func, trigger, ...)` | `Job` | Register a job. The callable is stored locally; only a picklable reference is sent to APScheduler. |
| `cron(expression, job_id)` | `Decorator` | Decorator for cron-scheduled methods. |
| `interval(**kwargs)` | `Decorator` | Decorator for fixed-interval methods. |
| `remove_job(job_id)` | `None` | Remove the job from the scheduler and the local registry. |
| `pause_job(job_id)` | `None` | Suspend a job without removing it. |
| `resume_job(job_id)` | `None` | Resume a paused job. |
| `jobs()` | `list[dict]` | List all active jobs with their next run time. |
| `status()` | `dict` | Returns service status, job count, timezone, and `distributed_lock` flag. |

---

### YAML Configuration

```yaml linenums="1" title="xcore.yaml"
services:
  scheduler:
    enabled: true           # bool — Enable/disable the service. Default: true
    backend: "memory"       # str — "memory" | "redis". Default: "memory"
    timezone: "UTC"         # str — Standard IANA timezone. Default: "UTC"
    url: ~                  # str — Required when backend is "redis"

    jobs:                   # (1)!
      - id: "global_sync"
        func: "myapp.tasks:sync_data"
        trigger: "interval"
        hours: 1
```

1.  **Static jobs** declared here are registered at startup, independently of any plugin.

#### Job defaults (applied to every job)

| Option | Value | Description |
|--------|-------|-------------|
| `coalesce` | `True` | Merge missed triggers into a single run instead of executing one per missed interval |
| `max_instances` | `1` | Prevent concurrent executions of the same job on the same worker |
| `misfire_grace_time` | `60 s` | Cancel a job if it is more than 60 seconds late |

---

### Scaling

No extra configuration is needed. When `backend: redis`:

- All workers share the same APScheduler job store via Redis.
- Each worker registers its own jobs at startup via `ScheduledMixin.on_load`.
- The built-in distributed lock ensures exactly-once execution per trigger.

For true single-executor semantics (e.g., expensive cron jobs that must never run twice), you can lower `_LOCK_TTL` in the service or implement your own idempotency in the job function.

---

### Common Errors & Pitfalls

!!! danger "ImportError: APScheduler not installed"
    Xcore does not bundle APScheduler by default.
    **Fix**: `pip install apscheduler`

!!! warning "Async/Sync Mixup"
    All scheduled functions should be `async def`. Synchronous callables are supported but will block the event loop.

!!! failure "Duplicate Job IDs"
    `add_job` defaults to `replace_existing=True`, so re-registering a job on plugin reload is safe.

!!! info "Lock TTL and long-running jobs"
    The distributed lock TTL is 300 seconds by default. If a job regularly takes longer, increase `_LOCK_TTL` in `xcore/services/scheduler/service.py` or split the job into smaller tasks.

---

### Best Practices

!!! success "Use meaningful job IDs"
    Always set an explicit `job_id` so you can pause, resume, or remove the job by name.

!!! tip "Always set a timezone"
    Configure `timezone: Europe/Paris` (or your local zone) to avoid DST surprises with cron expressions.

!!! tip "Keep job functions thin"
    Delegate heavy work to a separate async service or worker. The scheduler should only orchestrate, not process.
