---
title: Scheduler Decorators
description: "@cron and @interval decorators for declarative APScheduler job registration."
icon: material/timer
---

# Scheduler

xcoreSDK wraps APScheduler to provide declarative job scheduling via two decorators: `@cron` for calendar-based schedules and `@interval` for fixed-interval polling.

```python
from xcore.sdk import cron, interval
```

Jobs are registered during `on_load` and removed during `on_unload` — no manual lifecycle management required.

---

## @cron

Schedules a method using a 5-field cron expression.

```python
from xcore.sdk import cron

@cron("0 3 * * *")              # daily at 03:00
async def nightly_cleanup(self) -> None:
    self.logger.info("running cleanup")

@cron("0 9 * * MON-FRI")       # weekdays at 09:00
async def morning_report(self) -> None:
    ...

@cron("*/15 * * * *")           # every 15 minutes
async def poll(self) -> None:
    ...
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `expression` | `str` | — | 5-field cron: `minute hour day month weekday` |
| `job_id` | `str \| None` | `None` | Explicit job ID; defaults to `{plugin}.{method}` |

**Cron field reference**

```
┌─────────────  minute       (0–59)
│ ┌───────────  hour         (0–23)
│ │ ┌─────────  day of month (1–31)
│ │ │ ┌───────  month        (1–12 or JAN–DEC)
│ │ │ │ ┌─────  day of week  (0–6 or SUN–SAT or MON–FRI)
│ │ │ │ │
* * * * *
```

Common examples:

| Expression | Meaning |
|------------|---------|
| `0 * * * *` | Every hour at :00 |
| `0 0 * * *` | Daily at midnight |
| `0 9 * * MON-FRI` | Weekdays at 09:00 |
| `0 0 1 * *` | First day of every month |
| `*/5 * * * *` | Every 5 minutes |

---

## @interval

Schedules a method to run on a fixed time interval.

```python
from xcore.sdk import interval

@interval(seconds=30)
async def heartbeat(self) -> None:
    self.logger.debug("alive")

@interval(minutes=5)
async def sync(self) -> None:
    ...

@interval(hours=1)
async def hourly_flush(self) -> None:
    ...
```

**Parameters** (keyword arguments only; at least one required)

| Name | Type | Description |
|------|------|-------------|
| `seconds` | `int \| float` | Interval in seconds |
| `minutes` | `int \| float` | Interval in minutes |
| `hours` | `int \| float` | Interval in hours |
| `days` | `int \| float` | Interval in days |

Multiple units can be combined: `@interval(hours=1, minutes=30)` runs every 90 minutes.

---

## ScheduledMixin

Composed by `AutoMixin`. Scans the plugin class for `@cron` and `@interval` decorated methods during `on_load` and registers each as an APScheduler job via `self.ctx.scheduler`.

During `on_unload`, all jobs registered by this plugin are removed.

### Job ID format

If `job_id` is not specified in `@cron`, the scheduler generates: `{plugin_name}.{method_name}`.

Explicit IDs are useful when you need to cancel or inspect a specific job from another plugin:

```python
@cron("0 2 * * *", job_id="demo.cleanup.nightly")
async def cleanup(self) -> None:
    ...
```

---

## Error handling

If a scheduled job raises an exception, APScheduler logs the traceback and reschedules normally. The exception does **not** propagate to the plugin or crash the process.

For custom error handling within a job:

```python
@interval(minutes=10)
async def sync(self) -> None:
    try:
        await self._do_sync()
    except Exception as e:
        self.logger.error("sync failed: %s", e)
```
