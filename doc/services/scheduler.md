---
title: Scheduler Service
description: Background task scheduling for Xcore using APScheduler.
icon: material/calendar-clock
---

# Scheduler Service

The `SchedulerService` allows you to schedule asynchronous background tasks directly within your Xcore application. It is built on top of [APScheduler](https://apscheduler.readthedocs.io/) and supports a wide range of triggers, including interval-based, date-based (one-shot), and standard cron expressions.

---

### Prerequisites

- [x] [Service Container](./services.md) overview understood
- [x] `apscheduler` package installed (`pip install apscheduler`)
- [ ] `redis` driver (only if using the Redis job store)

---

### Key Concepts

#### The Async Scheduler
Xcore uses the `AsyncIOScheduler`, ensuring that scheduled tasks run within the framework's main event loop without blocking or requiring complex threading logic.

#### Job Persistence
- **Memory Store**: Default. Jobs are lost when the server restarts.
- **Redis Store**: Recommended for production. Jobs are persisted in Redis, allowing them to survive restarts and even migrate between server instances.

---

### Practical Guide

#### 1. Using Decorators
The simplest way to schedule tasks in a Trusted plugin is using the `@scheduler` decorators.

```python linenums="1"
from xcore import TrustedBase

class Plugin(TrustedBase):
    async def on_start(self):
        scheduler = self.get_service("scheduler")

        @scheduler.interval(minutes=5)
        async def check_updates():
            print("Checking for updates...")

        @scheduler.cron("0 3 * * *")  # (1)!
        async def nightly_cleanup():
            print("Running nightly cleanup...")
```

1.  Standard 5-part cron expression (minute, hour, day, month, day_of_week).

#### 2. Manual Job Management
You can add and remove jobs dynamically during the application's runtime.

```python linenums="1"
async def handle(self, action, payload):
    scheduler = self.get_service("scheduler")

    if action == "schedule_reminder":
        # Add a one-shot job
        scheduler.add_job(
            self.send_reminder,
            trigger="date",
            run_date=payload["time"],
            args=[payload["user_id"]],
            job_id=f"reminder_{payload['id']}"
        )
        return {"status": "ok"}
```

---

### API Reference

#### `SchedulerService` Methods
| Method | Return Type | Description |
|--------|-------------|-------------|
| `add_job(func, trigger, ...)` | `Job` | Low-level access to the APScheduler `add_job` method. |
| `interval(seconds, minutes, ...)` | `Decorator` | Decorator for periodic tasks. |
| `cron(expression)` | `Decorator` | Decorator for tasks using a cron expression string. |
| `remove_job(job_id)` | `None` | Stop and remove a scheduled task. |
| `pause_job(job_id)` | `None` | Temporarily suspend a job. |
| `resume_job(job_id)` | `None` | Resume a previously paused job. |
| `jobs()` | `list[dict]` | List all currently active jobs and their next run times. |

---

### YAML Configuration

```yaml linenums="1" title="xcore.yaml"
services:
  scheduler:
    enabled: true        # bool — Enable/disable the service. Default: true
    backend: "memory"    # str — "memory" | "redis". Default: "memory"
    timezone: "UTC"      # str — Standard IANA timezone. Default: "UTC"
    url: ~               # str — Required for Redis backend. Default: null

    jobs:                # (1)!
      - id: "global_sync"
        func: "myapp.tasks:sync_data"
        trigger: "interval"
        hours: 1
```

1.  **Global Jobs**: You can declare static jobs that run independently of any plugin lifecycle.

---

### Common Errors & Pitfalls

!!! danger "ImportError: APScheduler not installed"
    Xcore does not bundle APScheduler by default.
    **Fix**: Run `pip install apscheduler` in your environment.

!!! warning "Async/Sync Mixup"
    The scheduler runs in an `asyncio` loop. While it can run synchronous functions using `to_thread`, it is highly recommended to use `async def` for all your tasks.

!!! failure "Duplicate Job IDs"
    If you try to add a job with an ID that already exists, the framework will overwrite the existing job if `replace_existing: true` (default) or raise a `ConflictingIdError`.

---

### Best Practices

!!! success "Manage Plugin Job Lifecycles"
    If you add jobs dynamically in `on_start()`, ensure you assign meaningful `job_id`s so you can identify and potentially remove them later.

!!! tip "Use Timezones"
    Always specify a `timezone` in your configuration (e.g., `Europe/Paris`) to avoid confusion with Daylight Saving Time transitions.
