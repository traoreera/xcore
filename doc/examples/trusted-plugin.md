# Example: Trusted Task Manager (Advanced)

This comprehensive example demonstrates a production-grade **Trusted** plugin with a modular architecture, database persistence, notifications, and complex business logic.

---

## 1. Plugin Structure

```text
plugins/task_manager/
├── plugin.yaml           # Plugin manifest
├── .env                  # Local configuration
└── src/
    ├── __init__.py
    ├── main.py          # Main entry point
    ├── router.py        # FastAPI routes
    ├── models.py        # Data models
    ├── services.py      # Business logic
    └── repository.py    # Database access
```

---

## 2. Manifest (`plugin.yaml`)

```yaml
name: task_manager
version: 2.1.0
author: XCore Team
description: |
  Advanced task manager with:
  - Full CRUD via HTTP and IPC
  - Email notifications via external service
  - Statistics and reports
  - PostgreSQL/SQLite persistence

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

requires:
  - user_service  # Depends on the user service for assignment validation

permissions:
  - resource: "db.tasks.*"
    actions: ["read", "write", "delete"]
    effect: allow
  - resource: "ext.email_service"
    actions: ["send"]
    effect: allow
  - resource: "scheduler"
    actions: ["schedule", "cancel"]
    effect: allow

resources:
  timeout_seconds: 30
  rate_limit:
    calls: 1000
    period_seconds: 60
```

---

## 3. Data Models (`src/models.py`)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional, List

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    tags: List[str] = []

class Task(TaskCreate):
    id: int
    created_by: int
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 4. Business Services (`src/services.py`)

```python
from xcore.sdk import ok, error
from .models import TaskCreate, TaskStatus

class TaskService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.services.get("db")
        self.email = ctx.services.get("ext.email_service")
        self.scheduler = ctx.services.get("scheduler")

    async def create_task(self, data: TaskCreate, creator_id: int):
        try:
            # 1. Validate assignment via another plugin
            user_check = await self.ctx.plugins.call(
                "user_service", "exists", {"id": data.assigned_to}
            )
            if data.assigned_to and user_check.get("status") != "ok":
                return error("Assigned user does not exist", code="user_not_found")

            # 2. Persist to Database
            async with self.db.session() as session:
                task_id = await session.execute(
                    "INSERT INTO tasks (title, description, created_by, assigned_to) "
                    "VALUES (:t, :d, :c, :a) RETURNING id",
                    {"t": data.title, "d": data.description, "c": creator_id, "a": data.assigned_to}
                )

            # 3. Notify via Email (Side effect)
            if data.assigned_to:
                await self.email.send(
                    recipient_id=data.assigned_to,
                    subject=f"New Task: {data.title}",
                    body="You have been assigned a new task."
                )

            # 4. Schedule a reminder if due date exists
            if data.due_date:
                self.scheduler.add_job(
                    self._send_reminder,
                    trigger="date",
                    run_date=data.due_date,
                    args=[task_id]
                )

            return ok(id=task_id, message="Task created successfully")

        except Exception as e:
            self.ctx.logger.exception("Failed to create task")
            return error(str(e), code="internal_error")

    async def _send_reminder(self, task_id: int):
        # Implementation for reminder notification
        pass
```

---

## 5. Main Entry Point (`src/main.py`)

```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, RoutedPlugin, action, validate_payload
from .services import TaskService
from .models import TaskCreate
from .router import create_router

class Plugin(AutoDispatchMixin, RoutedPlugin, TrustedBase):
    """Advanced Task Manager Plugin."""

    async def on_load(self) -> None:
        # Initialize internal service
        self.service = TaskService(self.ctx)
        self.logger.info("Task Manager Loaded")

    def get_router(self):
        # Mount separate router file
        return create_router(self)

    @action("create")
    @validate_payload(TaskCreate)
    async def handle_create(self, payload: dict):
        # Dispatch to business service
        creator_id = self.ctx.get("user_id", 0)
        return await self.service.create_task(TaskCreate(**payload), creator_id)

    @action("stats")
    async def get_stats(self, payload: dict):
        # Return aggregated data
        return ok(total=150, completed=120, pending=30)
```
