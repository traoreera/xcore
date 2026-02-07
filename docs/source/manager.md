# manager - Plugin & Task Management Framework

## Overview

The `manager` module is the core framework for managing plugins and scheduled tasks. It provides dynamic plugin loading, hot reloading, sandboxing, and task scheduling with APScheduler.

## Module Structure

```
manager/
├── __init__.py           # Exports Manager, Loader, cfg
├── conf.py              # Configuration & database URL
├── db.py                # Database utilities
├── runtimer.py          # Runtime management
├── crud/                # CRUD operations
│   ├── plugin.py        # Plugin CRUD
│   └── taskcurd.py      # Task CRUD
├── models/              # SQLAlchemy models
│   ├── plugins.py       # Plugin model
│   └── tasks.py         # Task model
├── plManager/           # Plugin management core
│   ├── installer.py     # Plugin installation
│   ├── loader.py        # Dynamic plugin loading
│   ├── manager.py       # Plugin lifecycle management
│   ├── reloader.py      # Hot reload functionality
│   ├── repository.py    # Plugin repository/database
│   ├── snapshot.py      # Plugin state snapshots
│   └── validator.py     # Plugin validation
├── routes/              # API routes
│   └── task.py          # Task management endpoints
├── schemas/             # Pydantic schemas
│   ├── plugins.py       # Plugin schemas
│   └── taskManager.py   # Task schemas
├── task/                # Task execution
│   ├── corethread.py    # Core threading logic
│   └── taskmanager.py   # APScheduler task management
└── tools/               # Utilities
    ├── error.py         # Error handling
    └── trasactional.py  # Transaction management
```

## Core Components

### Manager (`__init__.py`)

Main entry point for the management framework.

**Exports:**
- `Manager` - Plugin and task manager instance
- `Loader` - Plugin loader instance
- `cfg` - Configuration instance

### Plugin Management (`plManager/`)

#### `manager.py`

Core plugin lifecycle management.

**Class:** `PluginManager`

```python
class PluginManager:
    """Manages plugin lifecycle: install, enable, disable, uninstall"""

    def install(self, plugin_path: str) -> Plugin:
        """Install a plugin from a path or package"""

    def enable(self, plugin_id: str) -> None:
        """Enable a plugin"""

    def disable(self, plugin_id: str) -> None:
        """Disable a plugin"""

    def uninstall(self, plugin_id: str) -> None:
        """Uninstall a plugin"""

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a plugin by ID"""

    def list_plugins(self) -> List[Plugin]:
        """List all installed plugins"""
```

#### `loader.py`

Dynamic plugin loading with cache purging.

**Class:** `PluginLoader`

```python
class PluginLoader:
    """Loads plugins dynamically with hot-reload support"""

    def load(self, plugin_id: str) -> ModuleType:
        """Load a plugin module"""

    def unload(self, plugin_id: str) -> None:
        """Unload a plugin and purge cache"""

    def reload(self, plugin_id: str) -> ModuleType:
        """Hot-reload a plugin"""

    def purge_cache(self, plugin_id: str) -> None:
        """Purge import cache for a plugin"""
```

#### `installer.py`

Plugin installation utilities.

```python
class PluginInstaller:
    """Handles plugin installation from various sources"""

    def install_from_path(self, path: str) -> Plugin:
        """Install plugin from filesystem path"""

    def install_from_package(self, package_name: str) -> Plugin:
        """Install plugin from PyPI package"""

    def install_from_zip(self, zip_path: str) -> Plugin:
        """Install plugin from zip archive"""
```

#### `validator.py`

Plugin validation.

```python
class PluginValidator:
    """Validates plugin structure and dependencies"""

    def validate_structure(self, plugin_path: str) -> bool:
        """Validate plugin directory structure"""

    def validate_dependencies(self, plugin: Plugin) -> bool:
        """Validate plugin dependencies"""

    def validate_manifest(self, manifest: dict) -> bool:
        """Validate plugin manifest"""
```

#### `reloader.py`

Hot reload functionality.

```python
class PluginReloader:
    """Handles hot reloading of plugins during development"""

    def watch(self, plugin_id: str) -> None:
        """Start watching a plugin for changes"""

    def unwatch(self, plugin_id: str) -> None:
        """Stop watching a plugin"""

    def on_change(self, plugin_id: str) -> None:
        """Handler called when plugin files change"""
```

#### `repository.py`

Plugin repository/database.

```python
class PluginRepository:
    """Manages plugin storage and retrieval"""

    def save(self, plugin: Plugin) -> None:
        """Save plugin to repository"""

    def get(self, plugin_id: str) -> Optional[Plugin]:
        """Get plugin from repository"""

    def delete(self, plugin_id: str) -> None:
        """Delete plugin from repository"""
```

#### `snapshot.py`

Plugin state snapshots.

```python
class PluginSnapshot:
    """Manages plugin state snapshots for rollback"""

    def create(self, plugin_id: str) -> Snapshot:
        """Create a snapshot of current plugin state"""

    def restore(self, snapshot_id: str) -> None:
        """Restore plugin from snapshot"""

    def list_snapshots(self, plugin_id: str) -> List[Snapshot]:
        """List all snapshots for a plugin"""
```

### Task Management (`task/`)

#### `taskmanager.py`

APScheduler-based task management.

**Class:** `TaskManager`

```python
class TaskManager:
    """Manages scheduled tasks with APScheduler"""

    def add_task(
        self,
        func: Callable,
        trigger: str,
        id: str,
        **kwargs
    ) -> Task:
        """Add a scheduled task"""

    def remove_task(self, task_id: str) -> None:
        """Remove a scheduled task"""

    def pause_task(self, task_id: str) -> None:
        """Pause a scheduled task"""

    def resume_task(self, task_id: str) -> None:
        """Resume a paused task"""

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""

    def list_tasks(self) -> List[Task]:
        """List all tasks"""

    def start(self) -> None:
        """Start the task scheduler"""

    def shutdown(self) -> None:
        """Shutdown the task scheduler"""
```

**Trigger Types:**
- `interval` - Run at fixed intervals
- `cron` - Run on cron schedule
- `date` - Run once at specific date

#### `corethread.py`

Core threading logic for task execution.

```python
class CoreThread:
    """Handles task execution in separate threads"""

    def execute(self, task: Task) -> None:
        """Execute a task in a thread"""

    def restart_on_failure(self, task: Task, max_retries: int = 3) -> None:
        """Auto-restart task on failure"""
```

### Models (`models/`)

#### `plugins.py`

```python
class Plugin(Base):
    """SQLAlchemy model for plugins"""

    id: str                    # Unique plugin ID
    name: str                  # Plugin name
    version: str               # Plugin version
    description: str           # Plugin description
    author: str                # Plugin author
    enabled: bool              # Is plugin enabled
    installed_at: datetime     # Installation timestamp
    path: str                  # Plugin filesystem path
    manifest: dict             # Plugin manifest
    dependencies: List[str]    # Plugin dependencies
```

#### `tasks.py`

```python
class Task(Base):
    """SQLAlchemy model for scheduled tasks"""

    id: str                    # Unique task ID
    name: str                  # Task name
    func_path: str             # Path to task function
    trigger: str               # Trigger type
    trigger_args: dict         # Trigger arguments
    enabled: bool              # Is task enabled
    max_retries: int           # Max retry attempts
    timeout: int               # Task timeout
    last_run: datetime         # Last execution time
    next_run: datetime         # Next scheduled run
    status: str                # Current status
```

### CRUD Operations (`crud/`)

#### `plugin.py`

```python
class PluginCRUD:
    """CRUD operations for plugins"""

    def create(self, plugin_data: PluginCreate) -> Plugin:
        """Create a new plugin record"""

    def read(self, plugin_id: str) -> Optional[Plugin]:
        """Read a plugin by ID"""

    def update(self, plugin_id: str, data: PluginUpdate) -> Plugin:
        """Update a plugin"""

    def delete(self, plugin_id: str) -> None:
        """Delete a plugin"""

    def list_all(self) -> List[Plugin]:
        """List all plugins"""
```

#### `taskcurd.py`

```python
class TaskCRUD:
    """CRUD operations for tasks"""

    def create(self, task_data: TaskCreate) -> Task:
        """Create a new task"""

    def read(self, task_id: str) -> Optional[Task]:
        """Read a task by ID"""

    def update(self, task_id: str, data: TaskUpdate) -> Task:
        """Update a task"""

    def delete(self, task_id: str) -> None:
        """Delete a task"""
```

### API Routes (`routes/`)

#### `task.py`

Task management API endpoints.

**Endpoints:**
```
GET    /manager/tasks           # List all tasks
POST   /manager/tasks           # Create new task
GET    /manager/tasks/{id}      # Get task details
PUT    /manager/tasks/{id}      # Update task
DELETE /manager/tasks/{id}      # Delete task
POST   /manager/tasks/{id}/run  # Run task immediately
POST   /manager/tasks/{id}/pause    # Pause task
POST   /manager/tasks/{id}/resume   # Resume task
```

### Schemas (`schemas/`)

#### `plugins.py`

```python
class PluginCreate(BaseModel):
    name: str
    version: str
    description: Optional[str]
    author: Optional[str]
    path: str

class PluginUpdate(BaseModel):
    name: Optional[str]
    version: Optional[str]
    enabled: Optional[bool]

class PluginRead(BaseModel):
    id: str
    name: str
    version: str
    enabled: bool
    installed_at: datetime
```

#### `taskManager.py`

```python
class TaskCreate(BaseModel):
    name: str
    func_path: str
    trigger: str
    trigger_args: dict
    max_retries: int = 3

class TaskUpdate(BaseModel):
    name: Optional[str]
    enabled: Optional[bool]
    trigger_args: Optional[dict]

class TaskRead(BaseModel):
    id: str
    name: str
    status: str
    last_run: Optional[datetime]
    next_run: Optional[datetime]
```

## Usage Examples

### Plugin Management

```python
from manager import Manager

# Install a plugin
plugin = Manager.install("/path/to/my_plugin")

# Enable the plugin
Manager.enable(plugin.id)

# List all plugins
plugins = Manager.list_plugins()

# Hot reload a plugin
Manager.reload(plugin.id)

# Uninstall a plugin
Manager.uninstall(plugin.id)
```

### Task Scheduling

```python
from manager import Manager

# Add an interval task
task = Manager.add_task(
    func=my_function,
    trigger="interval",
    id="cleanup_task",
    minutes=30
)

# Add a cron task
task = Manager.add_task(
    func=daily_report,
    trigger="cron",
    id="daily_report",
    hour=9,
    minute=0
)

# Pause a task
Manager.pause_task(task.id)

# Resume a task
Manager.resume_task(task.id)

# Remove a task
Manager.remove_task(task.id)
```

### Creating a Plugin

```python
# plugins/my_plugin/__init__.py

PLUGIN_INFO = {
    "id": "my_plugin",
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "A sample plugin",
    "author": "Developer",
    "dependencies": []
}

from fastapi import APIRouter

router = APIRouter(prefix="/my_plugin")

@router.get("/hello")
async def hello():
    return {"message": "Hello from My Plugin"}

# plugins/my_plugin/run.py
from manager.plManager.loader import Plugin

class Plugin(Plugin):
    def on_enable(self):
        """Called when plugin is enabled"""
        pass

    def on_disable(self):
        """Called when plugin is disabled"""
        pass
```

## Configuration

The manager module reads configuration from `config.json`:

```json
{
  "manager": {
    "plugins_directory": "plugins",
    "tasks_directory": "backgroundtask",
    "auto_enable": true,
    "hot_reload": true,
    "sandboxing": true
  }
}
```

## Dependencies

- `apscheduler` - Task scheduling
- `sqlalchemy` - Database ORM
- `configurations` - Configuration management
- `loggers` - Logging system
- `hooks` - Hook system

## Related Documentation

- [plugins.md](plugins.md) - Plugin development
- [hooks.md](hooks.md) - Hook system
- [configurations.md](configurations.md) - Configuration system
