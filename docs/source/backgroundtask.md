# backgroundtask - Background Task Container

## Overview

The `backgroundtask` module serves as a container for APScheduler background tasks. It provides a location for task definitions that can be loaded and scheduled by the manager module.

## Module Structure

```
backgroundtask/
└── taskplugins.py         # Task plugin container
```

## Core Components

### Task Container (`taskplugins.py`)

```python
# taskplugins.py

from manager.task.taskmanager import TaskManager
from manager.schemas.taskManager import TaskCreate
from loggers import get_logger

logger = get_logger("backgroundtask")

# Define background tasks here

async def cleanup_old_logs():
    """
    Cleanup old log entries.
    Runs daily at midnight.
    """
    logger.info("Starting log cleanup task")
    # Implementation here
    logger.info("Log cleanup completed")

async def send_daily_reports():
    """
    Send daily summary reports.
    Runs every day at 9 AM.
    """
    logger.info("Sending daily reports")
    # Implementation here
    logger.info("Daily reports sent")

async def sync_external_data():
    """
    Synchronize data with external services.
    Runs every hour.
    """
    logger.info("Starting data sync")
    # Implementation here
    logger.info("Data sync completed")

async def health_check():
    """
    System health check.
    Runs every 5 minutes.
    """
    # Check system health
    pass

# Task definitions for auto-registration
TASK_DEFINITIONS = [
    {
        "id": "cleanup_old_logs",
        "name": "Cleanup Old Logs",
        "func": cleanup_old_logs,
        "trigger": "cron",
        "trigger_args": {"hour": 0, "minute": 0},
        "enabled": True,
        "max_retries": 3,
        "timeout": 300
    },
    {
        "id": "send_daily_reports",
        "name": "Send Daily Reports",
        "func": send_daily_reports,
        "trigger": "cron",
        "trigger_args": {"hour": 9, "minute": 0},
        "enabled": True,
        "max_retries": 2,
        "timeout": 600
    },
    {
        "id": "sync_external_data",
        "name": "Sync External Data",
        "func": sync_external_data,
        "trigger": "interval",
        "trigger_args": {"hours": 1},
        "enabled": False,  # Disabled by default
        "max_retries": 3,
        "timeout": 1800
    },
    {
        "id": "health_check",
        "name": "System Health Check",
        "func": health_check,
        "trigger": "interval",
        "trigger_args": {"minutes": 5},
        "enabled": True,
        "max_retries": 1,
        "timeout": 30
    }
]

def register_tasks(task_manager: TaskManager):
    """
    Register all tasks with the task manager.

    Args:
        task_manager: TaskManager instance
    """
    for task_def in TASK_DEFINITIONS:
        try:
            task_manager.add_task(
                func=task_def["func"],
                trigger=task_def["trigger"],
                id=task_def["id"],
                **task_def["trigger_args"],
                max_retries=task_def.get("max_retries", 3),
                timeout=task_def.get("timeout", 300)
            )
            logger.info(f"Registered task: {task_def['name']}")
        except Exception as e:
            logger.error(f"Failed to register task {task_def['id']}: {e}")
```

## Task Triggers

### Interval Trigger

Run at fixed intervals.

```python
{
    "trigger": "interval",
    "trigger_args": {
        "weeks": 0,
        "days": 0,
        "hours": 1,
        "minutes": 0,
        "seconds": 0
    }
}
```

### Cron Trigger

Run on a schedule.

```python
{
    "trigger": "cron",
    "trigger_args": {
        "year": "*",          # 4-digit year
        "month": "*",         # 1-12
        "day": "*",           # 1-31
        "week": "*",          # 1-53
        "day_of_week": "*",   # 0-6 or mon,tue,wed,thu,fri,sat,sun
        "hour": "*",          # 0-23
        "minute": "*",        # 0-59
        "second": 0           # 0-59
    }
}

# Examples
{"hour": 9, "minute": 0}           # Daily at 9:00 AM
{"day_of_week": "mon", "hour": 9}  # Every Monday at 9:00 AM
{"minute": "*/15"}                  # Every 15 minutes
{"hour": "*/2"}                     # Every 2 hours
```

### Date Trigger

Run once at a specific time.

```python
{
    "trigger": "date",
    "trigger_args": {
        "run_date": "2024-12-25 00:00:00"
    }
}
```

## Usage Examples

### Creating a New Task

```python
# backgroundtask/taskplugins.py

from database.db import SessionLocal
from loggers import get_logger

logger = get_logger("backgroundtask")

async def cleanup_expired_sessions():
    """Remove expired user sessions"""
    db = SessionLocal()
    try:
        from auth.models import UserSession
        from datetime import datetime

        expired = db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).all()

        for session in expired:
            db.delete(session)

        db.commit()
        logger.info(f"Cleaned up {len(expired)} expired sessions")
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        raise
    finally:
        db.close()

# Add to TASK_DEFINITIONS
TASK_DEFINITIONS = [
    # ... existing tasks ...
    {
        "id": "cleanup_expired_sessions",
        "name": "Cleanup Expired Sessions",
        "func": cleanup_expired_sessions,
        "trigger": "cron",
        "trigger_args": {"hour": "*/6"},  # Every 6 hours
        "enabled": True,
        "max_retries": 3,
        "timeout": 300
    }
]
```

### Task with Dependencies

```python
# backgroundtask/taskplugins.py

from cache import CacheManager
from database.db import SessionLocal
from loggers import get_logger

logger = get_logger("backgroundtask")
cache = CacheManager()

async def refresh_cache_data():
    """Refresh cached data from database"""
    db = SessionLocal()
    try:
        # Fetch fresh data
        from plugins.my_plugin.models import Product

        products = db.query(Product).all()

        # Update cache
        for product in products:
            await cache.set(
                f"product:{product.id}",
                product.to_dict(),
                ttl=3600
            )

        logger.info(f"Refreshed {len(products)} products in cache")
    finally:
        db.close()
```

### Conditional Task Execution

```python
# backgroundtask/taskplugins.py

from configurations import Xcorecfg
from loggers import get_logger

logger = get_logger("backgroundtask")
config = Xcorecfg.from_file("config.json")

async def premium_only_task():
    """Task that only runs in premium mode"""
    if not config.premium_features_enabled:
        logger.info("Skipping premium task - not enabled")
        return

    # Execute premium task
    logger.info("Running premium task")
```

### Error Handling and Retries

```python
# backgroundtask/taskplugins.py

from loggers import get_logger
import asyncio

logger = get_logger("backgroundtask")

async def api_sync_task():
    """Sync with external API with retry logic"""
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            # Attempt API call
            result = await call_external_api()
            logger.info("API sync successful")
            return result
        except Exception as e:
            logger.warning(f"API sync attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.error("API sync failed after all retries")
                raise
```

## Configuration

Configuration in `config.json`:

```json
{
  "manager": {
    "tasks_directory": "backgroundtask",
    "max_tasks": 50,
    "task_timeout": 300,
    "auto_restart_tasks": true,
    "max_task_retries": 3,
    "scheduler_thread_pool": 10
  }
}
```

## Registering Tasks

### Automatic Registration

```python
# In application startup
from manager import Manager
from backgroundtask.taskplugins import register_tasks

async def startup_event():
    # Register background tasks
    register_tasks(Manager.task_manager)

    # Start scheduler
    Manager.task_manager.start()
```

### Manual Registration

```python
from manager.task.taskmanager import TaskManager
from backgroundtask.taskplugins import cleanup_old_logs

task_manager = TaskManager()

# Add single task
task_manager.add_task(
    func=cleanup_old_logs,
    trigger="cron",
    id="cleanup_logs",
    hour=0,
    minute=0
)

# Start scheduler
task_manager.start()
```

## Monitoring Tasks

### Task Status

```python
from manager import Manager

# List all tasks
tasks = Manager.task_manager.list_tasks()
for task in tasks:
    print(f"{task.id}: {task.status}")
    print(f"  Last run: {task.last_run}")
    print(f"  Next run: {task.next_run}")
```

### Task Logs

```python
from loggers import get_logger

logger = get_logger("backgroundtask")

async def monitored_task():
    logger.info("Task starting")
    try:
        # Task logic
        result = await do_work()
        logger.info(f"Task completed: {result}")
    except Exception as e:
        logger.exception("Task failed")
        raise
```

## Best Practices

### 1. Always Handle Exceptions

```python
async def robust_task():
    try:
        # Task logic
        pass
    except Exception as e:
        logger.exception("Task failed")
        # Don't let exceptions crash the scheduler
        raise  # Re-raise for retry logic
```

### 2. Use Timeouts

```python
import asyncio

async def task_with_timeout():
    try:
        await asyncio.wait_for(
            long_running_operation(),
            timeout=300  # 5 minutes
        )
    except asyncio.TimeoutError:
        logger.error("Task timed out")
```

### 3. Clean Up Resources

```python
async def resource_cleanup_task():
    db = SessionLocal()
    try:
        # Use database
        pass
    finally:
        db.close()  # Always close
```

### 4. Idempotent Tasks

```python
async def idempotent_task():
    """Task can run multiple times without side effects"""
    # Check if already processed
    if await is_already_processed():
        logger.info("Already processed, skipping")
        return

    # Process
    await do_processing()
    await mark_as_processed()
```

### 5. Logging

```python
from loggers import get_logger

logger = get_logger("backgroundtask")

async def well_logged_task():
    logger.info("Task starting")

    processed = 0
    errors = 0

    for item in items:
        try:
            await process(item)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to process {item}: {e}")
            errors += 1

    logger.info(f"Task complete: {processed} processed, {errors} errors")
```

## Testing Tasks

```python
import pytest
from backgroundtask.taskplugins import cleanup_old_logs

@pytest.mark.asyncio
async def test_cleanup_task():
    # Setup test data
    create_test_logs()

    # Run task
    await cleanup_old_logs()

    # Verify
    remaining = count_logs()
    assert remaining == 0

@pytest.mark.asyncio
async def test_task_error_handling():
    # Mock failure
    with pytest.raises(Exception):
        await failing_task()
```

## Troubleshooting

### Common Issues

1. **Tasks not running**
   - Check scheduler is started
   - Verify trigger configuration
   - Check task is enabled

2. **Tasks running multiple times**
   - Ensure idempotency
   - Check for duplicate registrations
   - Review trigger timing

3. **Memory leaks**
   - Close database sessions
   - Release file handles
   - Clear large objects

4. **Missed executions**
   - Check system time
   - Review scheduler thread pool
   - Check for blocking operations

## Dependencies

- `apscheduler` - Task scheduling
- `manager` - Task management
- `loggers` - Logging

## Related Documentation

- [manager.md](manager.md) - Task management
- [configurations.md](configurations.md) - Task configuration
