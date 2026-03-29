# Trusted Plugin Example (Advanced)

A complete example of a **Trusted** plugin with a modular architecture using a separate `router.py` and configuration via `.env`.

## Use Case: Task Manager

This plugin manages tasks with persistence, notifications, and advanced statistics.

## Plugin Structure

```text
plugins/task_manager/
├── plugin.yaml           # Plugin manifest
├── .env                  # Local configuration (not committed)
├── src/
│   ├── __init__.py
│   ├── main.py          # Main entry point
│   ├── router.py        # Separate FastAPI HTTP routes
│   ├── models.py        # Data models
│   └── services.py      # Business logic
└── data/
    └── .gitkeep         # Folder for local persistence
```

## 1. `plugin.yaml`

```yaml
name: task_manager
version: 2.0.0
author: XCore Team
description: |
  Advanced task manager with:
  - Full CRUD via HTTP and IPC
  - Email notifications
  - Statistics and reports
  - Database persistence

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

# Inter-plugin dependencies
requires:
  - users_plugin  # Requires users plugin for assignments

# Detailed permissions
permissions:
  - resource: "db.*"
    actions: ["read", "write", "delete"]
    effect: allow
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "ext.email*"
    actions: ["send"]
    effect: allow
  - resource: "scheduler"
    actions: ["schedule", "cancel"]
    effect: allow
  - resource: "audit.log"
    actions: ["write"]
    effect: allow

# Injected environment variables
env:
  TASKS_TABLE: "tasks"
  DEFAULT_PRIORITY: "medium"
  MAX_TASKS_PER_USER: "100"

# .env configuration
envconfiguration:
  inject: true
  required: true

# Allocated resources
resources:
  timeout_seconds: 30
  max_memory_mb: 256
  max_disk_mb: 100
  rate_limit:
    calls: 1000
    period_seconds: 60

# Runtime
runtime:
  health_check:
    enabled: true
    interval_seconds: 30
    timeout_seconds: 5
  retry:
    max_attempts: 3
    backoff_seconds: 1.0

# Filesystem
filesystem:
  allowed_paths: ["data/", "exports/"]
  denied_paths: ["src/config/"]

# Custom plugin configuration
notifications:
  email_template: "task_notification"
  enabled: true

priorities:
  levels: ["low", "medium", "high", "urgent"]
  default_days:
    low: 7
    medium: 3
    high: 1
    urgent: 0
```

## 2. `.env` (Local Configuration)

```bash
# Database Configuration
TASK_MANAGER_DB_URL=postgresql://localhost/taskmanager
TASK_MANAGER_DB_POOL_SIZE=10

# Notification Settings
TASK_MANAGER_SMTP_HOST=smtp.company.com
TASK_MANAGER_SMTP_PORT=587
TASK_MANAGER_SMTP_USER=notifications@company.com
TASK_MANAGER_SMTP_PASS=secure_password_here
TASK_MANAGER_NOTIFY_ON_ASSIGN=true
TASK_MANAGER_NOTIFY_ON_COMPLETE=true

# Feature Flags
TASK_MANAGER_ENABLE_ANALYTICS=true
TASK_MANAGER_ENABLE_EXPORTS=true
TASK_MANAGER_EXPORT_FORMATS=json,csv,pdf

# Security
TASK_MANAGER_ENCRYPTION_KEY=${TASK_MANAGER_SECRET_KEY}
TASK_MANAGER_MAX_EXPORT_SIZE_MB=50
```

## 3. `src/models.py`

```python
"""Data models for Task Manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Possible task statuses."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    """Task representation."""
    id: int | None = None
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_by: int = 0
    assigned_to: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    due_date: datetime | None = None
    completed_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Converts the task to a dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Creates a task from a dictionary."""
        return cls(
            id=data.get("id"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            priority=TaskPriority(data.get("priority", "medium")),
            created_by=data.get("created_by", 0),
            assigned_to=data.get("assigned_to"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
```

## 4. `src/services.py`

```python
"""Business services for Task Manager."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from xcore.sdk import ok, error

from .models import Task, TaskFilter, TaskStatus, TaskPriority


class TaskService:
    """Task management service."""

    def __init__(self, ctx, config: dict) -> None:
        self.ctx = ctx
        self.config = config
        self.db = ctx.services.get("db")
        self.cache = ctx.services.get("cache")
        self.email = ctx.services.get("ext.email")
        self.scheduler = ctx.services.get("scheduler")
        self.audit = ctx.services.get("audit.log")
        self.table = config.get("TASKS_TABLE", "tasks")
        self.max_per_user = int(config.get("MAX_TASKS_PER_USER", 100))

    async def create_task(self, task_data: dict, created_by: int) -> dict:
        """Creates a new task."""
        try:
            # Check task limit per user
            count = await self._count_user_tasks(created_by)
            if count >= self.max_per_user:
                return error(
                    f"Limit of {self.max_per_user} tasks reached",
                    code="limit_reached"
                )

            # Create task
            task = Task(
                title=task_data["title"],
                description=task_data.get("description", ""),
                priority=TaskPriority(task_data.get("priority", "medium")),
                created_by=created_by,
                assigned_to=task_data.get("assigned_to"),
                tags=task_data.get("tags", []),
                metadata=task_data.get("metadata", {}),
            )

            # Calculate due date if not provided
            if not task.due_date:
                days = self.config.get("priorities", {}).get("default_days", {}).get(
                    task.priority.value, 3
                )
                task.due_date = datetime.utcnow() + timedelta(days=days)

            # Persist to DB
            task.id = await self._insert_task(task)

            # Audit log
            await self._audit_log("task_created", task.id, created_by)

            # Notify if assigned
            if task.assigned_to and self.config.get("notifications", {}).get("enabled"):
                await self._notify_assignment(task)

            # Invalidate cache
            await self._invalidate_cache(f"user:{created_by}:tasks")

            return ok(task=task.to_dict())

        except Exception as e:
            return error(f"Task creation failed: {str(e)}", code="create_failed")

    # ... other service methods (implemented similar to the above)
```

## 5. `src/router.py`

```python
"""FastAPI HTTP routes for Task Manager."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Path, Body

from .models import TaskStatus, TaskPriority, TaskFilter


def create_router(plugin_instance) -> APIRouter:
    """
    Creates and configures the FastAPI router.
    """
    router = APIRouter(
        prefix="/tasks",
        tags=["tasks"],
    )
    service = plugin_instance.task_service

    @router.get("/", response_model=dict)
    async def list_tasks(
        status: list[TaskStatus] = Query(None),
        priority: list[TaskPriority] = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        """Lists tasks with filtering and pagination."""
        filters = TaskFilter(status=status, priority=priority)
        result = await service.list_tasks(filters, page, page_size)
        return result

    @router.post("/", response_model=dict, status_code=201)
    async def create_task(
        title: str = Body(..., min_length=1, max_length=200),
        priority: TaskPriority = Body(TaskPriority.MEDIUM),
    ):
        """Creates a new task."""
        current_user_id = plugin_instance.ctx.get("user_id", 0)
        result = await service.create_task({"title": title, "priority": priority.value}, current_user_id)
        return result

    return router
```

## 6. `src/main.py`

```python
"""Task Manager plugin entry point."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from xcore.sdk import TrustedBase, ok, error, action

from .services import TaskService
from .router import create_router


class Plugin(TrustedBase):
    """
    Task Manager Plugin - Trusted Version.
    """

    def __init__(self) -> None:
        super().__init__()
        self.task_service: TaskService | None = None
        self.config: dict[str, Any] = {}

    async def on_load(self) -> None:
        """Plugin initialization."""
        self._load_config()
        self.task_service = TaskService(self.ctx, self.config)

    def _load_config(self) -> None:
        """Loads configuration from environment."""
        env_config = self.ctx.env if self.ctx else {}
        self.config = {**env_config}

    def get_router(self) -> APIRouter | None:
        """Provides the FastAPI router."""
        if not self.task_service:
            return None
        return create_router(self)

    async def handle(self, action: str, payload: dict) -> dict:
        """Dispatches IPC actions."""
        # IPC handling logic...
        return ok()
```
