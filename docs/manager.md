# Module Documentation: manager/

The `manager/` module is the heart of the `xcore` framework, responsible for dynamically managing plugins, orchestrating background tasks, and providing core services for the application. It acts as a central control plane for the modular ecosystem.

## Top-Level Files and Their Roles

*   **`manager/__init__.py`**: (Likely empty or for package initialization). It's also where the `Manager` class (the core plugin manager) is likely instantiated and exported.
*   **`manager/conf.py`**: Handles loading of the manager-specific configuration from `config.json` (via `configurations.manager.ManagerCfg`) and environment variables (via `python-dotenv`). It also defines the `Database` class for database connection URL.
*   **`manager/db.py`**: Manages the database connection and session for the `manager` module's internal data (e.g., plugin and task metadata). It uses SQLAlchemy and provides a `get_db()` dependency for manager-specific routes and services.
*   **`manager/runtimer.py`**: The orchestrator for background tasks and services. It initializes `TaskManager` (for scheduling), `ModuleRuntimeManager` (for discovering and loading task modules), and `ServiceManager` (for managing background processes). It defines `on_startup()` and `on_shutdown()` hooks for managing the lifecycle of these services.
*   **`manager/test.html`**: A static HTML file, likely used for testing or as a placeholder.

## Subdirectories Overview

### `manager/crud/`

This subdirectory contains the Create, Read, Update, Delete (CRUD) operations for the manager's internal data, specifically for plugins and tasks. It interacts directly with the database models defined in `manager/models/`.

*   **`manager/crud/plugin.py`**:
    *   Defines the `PluginsCrud` class, which provides methods for `add`, `delete`, `update`, `get`, `get_all`, `get_all_active`, `get_all_not_active`, and `status` (activate/deactivate) of plugin records in the database.
    *   Uses `manager.models.plugins.PluginsModels` and `manager.schemas.plugins` for data interaction.
    *   Leverages `manager.tools.trasactional.Transactions` decorator for atomic database operations.
*   **`manager/crud/taskcurd.py`**:
    *   Defines the `ModuleRuntimeManager` class, central to managing background task modules.
    *   **Module Discovery**: Scans a configured directory (`backgroundtask/`) for Python task files (`.py`).
    *   **Metadata Extraction**: Imports task modules to extract their `metadata` attribute.
    *   **Registration**: Registers new task modules in the database (`TaskModel`).
    *   **Dynamic Loading**: Dynamically imports and executes task modules, looking for a `service_main` function as the task's entry point.
    *   **Directory Watching**: Uses `watchdog` to monitor the task directory for new files and automatically registers them.

### `manager/models/`

This subdirectory defines the SQLAlchemy ORM models used by the `manager` module to persist metadata about plugins and tasks in the database. These models are crucial for the manager's ability to track and manage the various modular components.

*   **`manager/models/plugins.py`**:
    *   Defines the `PluginsModels` SQLAlchemy model, which maps to the `plugins` table in the database.
    *   Stores metadata about each registered plugin, including its `id` (UUID string), `name`, `version`, `author`, `Api_prefix`, `tag_for_identified`, `trigger` (e.g., how often it runs), `add_time`, `update_time`, and `active` status.
    *   Includes `__init__` for instantiation from a Pydantic schema and utility `response_model()` / `response()` methods for API representation.
*   **`manager/models/tasks.py`**:
    *   Defines the `TaskModel` SQLAlchemy model, which maps to the `tasks` table in the database.
    *   Stores metadata about each discovered or registered background task, such as `id`, `title`, `type`, `module` name, `moduleDir`, `status`, `description`, `version`, `author`, and `metaFile` (a JSON column for storing arbitrary additional metadata).
    *   Includes `__init__` for instantiation from a Pydantic schema and a `ResponseModel()` method for API representation.

### `manager/plManager/`

This subdirectory contains the core logic and components responsible for the dynamic management, loading, and hot-reloading of plugins. It orchestrates the entire plugin lifecycle, from discovery and installation to validation and integration with the FastAPI application.

*   **`manager/plManager/installer.py`**:
    *   Defines the `Installer` class, which manages the isolated Python environments for plugins.
    *   Uses `poetry install` to install dependencies specified in a plugin's `pyproject.toml` within its own virtual environment.
    *   Ensures that plugin-specific `site-packages` directories are added to `sys.path` for correct module resolution.
*   **`manager/plManager/loader.py`**:
    *   Defines the `Loader` class, a central component for plugin discovery, loading, and integration.
    *   **Cache Purging**: Manages `sys.modules` to allow for clean re-importing during hot-reloads.
    *   **Discovery**: Scans the `plugins/` directory to find available plugin modules.
    *   **Loading & Initialization**: Dynamically imports plugin modules, performs initial validation, and adds new plugins to the database via the `Repository`. It also triggers dependency installation via `Installer` if needed.
    *   **FastAPI Integration**: Attaches plugin-defined FastAPI `APIRouter` instances to the main application, handling route conflicts and regenerating the OpenAPI schema.
    *   **Asynchronous Execution**: Provides methods to run plugin tasks asynchronously.
    *   **FastAPI Lifecycle Binding**: Binds to FastAPI's `on_event("startup")` hook to automatically load and attach plugins at application startup.
*   **`manager/plManager/manager.py`**:
    *   Defines the top-level `Manager` class (the one instantiated in `xcore/manage.py`). This class acts as the main orchestrator for the entire plugin system.
    *   Initializes and integrates `Loader`, `Snapshot`, and `Reloader` components.
    *   Manages the `plugins/` directory structure.
    *   **Hot-Reloading Loop**: Implements `start_watching`, a continuous loop that uses `Snapshot` to detect changes in the `plugins/` directory and triggers plugin reloads (`run_plugins`) when changes occur.
*   **`manager/plManager/reloader.py`**:
    *   Defines the `Reloader` class, which handles the dynamic updating of the FastAPI application's routes during a hot-reload event.
    *   **Route Purging**: Removes old plugin routes from the FastAPI application while preserving core routes.
    *   **OpenAPI Regeneration**: Forces the regeneration of the OpenAPI schema (used by Swagger UI/ReDoc) to reflect the updated routes.
    *   **Plugin Execution**: Facilitates the dynamic inclusion of new/updated plugin routers into the application.
*   **`manager/plManager/repository.py`**:
    *   Defines the `Repository` class, which provides an abstraction layer over the `PluginsCrud` (from `manager/crud/plugin.py`).
    *   Offers simplified methods for interacting with the database to manage plugin records (e.g., getting active plugins, adding new ones, enabling/disabling them).
*   **`manager/plManager/snapshot.py`**:
    *   Defines the `Snapshot` class, crucial for detecting file system changes in the `plugins/` directory.
    *   **File Hashing**: Computes SHA256 hashes of files to determine their content.
    *   **Ignore Patterns**: Uses configurable patterns (from `config.json`) to ignore hidden files, specific extensions, or filenames.
    *   **Snapshot Creation**: Generates a "snapshot" (a dictionary of file paths and their hashes) of a directory's state.
    *   **Change Detection**: Compares two snapshots to identify added, removed, or modified files, which triggers the hot-reloading mechanism.
*   **`manager/plManager/validator.py`**:
    *   Defines the `Validator` class, responsible for ensuring that plugin modules adhere to the expected structure and contain necessary metadata.
    *   **Plugin Structure Validation**: Checks for the presence of the `PLUGIN_INFO` dictionary within a plugin module and verifies that it contains required keys (e.g., "name", "version", "author").
    *   **Entry Point Validation**: Ensures that the plugin module defines a `Plugin` class with an expected entry method (e.g., `run`).

### `manager/routes/`

This subdirectory defines the API endpoints exposed by the `manager` module, primarily for controlling and monitoring background tasks, services, and the manager's configuration. These routes are integral for administering the `xcore` system via its API.

*   **`manager/routes/task.py`**:
    *   Defines the `task` FastAPI `APIRouter` with various endpoints for managing tasks and system metrics.
    *   **Resource Monitoring**: `GET /tasks/resources` to check CPU, RAM usage of active services.
    *   **Task Lifecycle**: `POST /tasks/start`, `POST /tasks/stop`, `POST /tasks/restart` to control background tasks.
    *   **Task Listing**: `GET /tasks/list` to view task status.
    *   **Task Metadata**: `GET /tasks/meta` to retrieve metadata for a specific task module.
    *   **Scheduler & Cron Jobs**: `GET /tasks/scheduler` and `GET /tasks/cron` to inspect scheduled tasks and cron jobs.
    *   **System Metrics**: `GET /tasks/metrics` for global CPU, memory, and active thread counts.
    *   **Service Summary**: `GET /tasks/summary` for an overview of all managed services (status, uptime).
    *   **Configuration Management**: `GET /tasks/config`, `POST /tasks/config/update`, `POST /tasks/reload`, `POST /tasks/config/autorestart` to interact with the manager's configuration.
    *   **Thread Listing**: `GET /tasks/threads` to list all active Python threads.
    *   **Access Control**: Most endpoints are protected by `admin.dependencies.require_admin` or `admin.dependencies.require_superuser`, ensuring only authorized users can perform these administrative actions.

### `manager/schemas/`

This subdirectory defines Pydantic schemas for data validation and serialization related to plugins, tasks, and API responses within the `manager` module. These schemas ensure consistent data structures for incoming requests and outgoing responses.

*   **`manager/schemas/plugins.py`**:
    *   **`Plugin`**: A `BaseModel` for representing the core metadata of a plugin (name, version, author, API prefix, tags, trigger). Used for adding new plugins to the database.
    *   **`Delete`**: A `BaseModel` for specifying the `name` and `id` of a plugin to be deleted.
    *   **`Update`**: A `BaseModel` for providing updated metadata when modifying an existing plugin's details.
    *   **`TaskManager`**: **(Note: This schema is named `TaskManager` but is located in `plugins.py`, which can be confusing. It defines the structure for background tasks, not plugin management specifically.)** This `BaseModel` represents the metadata for a task, including `title`, `type`, `module` name, `moduleDir`, `status`, `description`, `version`, `author`, and `metaFile` (for arbitrary JSON metadata). This schema is used when tasks are registered in the manager's database.
*   **`manager/schemas/taskManager.py`**:
    *   **`TaskResource`**: Defines the data structure for reporting resource usage of a single task (thread ID, CPU time, duration, memory, retries).
    *   **`TaskResourcesResponse`**: A `RootModel` used to wrap a dictionary of `TaskResource` instances, providing a structured response for resource monitoring endpoints.
    *   **`TaskStatusResponse`**: A simple `BaseModel` indicating the `name` and current `status` of a service.
    *   **`TaskListResponse`**: A `BaseModel` containing a list of task statuses, used for listing all active tasks.
    *   **`RestartService`**: Extends `TaskStatusResponse` to include a `success` boolean, providing a response for task restart operations.

### `manager/task/`

This subdirectory provides the core functionalities for managing and executing background tasks and scheduled jobs within the `manager` module. It combines threading for long-running services with a powerful scheduler for time-based events.

*   **`manager/task/corethread.py`**:
    *   Defines the `ThreadedService` class, a generic wrapper for running any callable (`target`) in a dedicated `threading.Thread`. It provides methods for `start`, `stop`, and `restart`, handles exceptions, and tracks service lifecycle (start time, running status).
    *   Defines the `ServiceManager` class, an orchestrator for multiple `ThreadedService` instances. It allows adding, removing, listing, stopping, and restarting services. Crucially, it includes an **auto-restart mechanism** for crashed services, configurable with retry limits (from `config.json`). It can also report resource usage (CPU, memory, duration) for services if `psutil` is installed.
*   **`manager/task/taskmanager.py`**:
    *   Defines the `TaskManager` class, which integrates with `APScheduler` (Advanced Python Scheduler) to manage scheduled background jobs.
    *   Initializes and starts a `BackgroundScheduler`.
    *   Provides methods to `add_job` (for single or multiple jobs), `reload_jobs` (to update scheduled tasks dynamically), `stop` the scheduler, `get_jobs_info` (to inspect active jobs), and `stopOne` (to stop a specific job).
    *   Supports various job triggers like interval-based and cron-like scheduling.

### `manager/tools/`

This subdirectory contains utility functions and decorators used across the `manager` module, primarily for robust error handling and ensuring data integrity in database operations.

*   **`manager/tools/error.py`**:
    *   Defines an `ExceptionResponse` Pydantic model for standardized error reporting (type, message, extension).
    *   Provides the `Error` class with an `exception_handler` static method. This method acts as a decorator, wrapping functions to:
        *   Automatically log the execution time of the wrapped function.
        *   Catch any `Exception` that occurs during function execution, log the error (including traceback), and return a structured error dictionary.
        *   **Note**: There appear to be some inconsistencies in the implementation of static methods (`__info`, `__warning`, `__error`, `Exception_Response`) within the `Error` class, where they might be incorrectly designed to be called with `self` or have other design quirks.
*   **`manager/tools/trasactional.py`**: **(Note: Typo in filename, should be `transactional.py`)**
    *   Defines the `Transactions` class with a `transactional` static method.
    *   This method serves as a decorator to ensure **transactional integrity** for database operations.
    *   When applied to a function (typically a CRUD method that accepts a `Session` object), it automatically performs:
        *   `self.db.commit()` if the wrapped function executes successfully.
        *   `self.db.rollback()` if any `Exception` occurs during execution, ensuring that incomplete database changes are undone.
    *   It also logs the execution time of the decorated function and warns about slow performance.

## Key Concepts and Functionality (Manager Module)

*   **Dynamic Plugin Management**: The `manager` module, through its `plManager` sub-module, handles the loading, reloading, and lifecycle of FastAPI plugins.
*   **Background Task Orchestration**: It discovers, registers, schedules, and executes background tasks, often defined within plugins or linked to the `backgroundtask/` directory.
*   **Internal Database**: The manager maintains its own database (configured via `manager/conf.py` and `manager/db.py`) to store metadata about active plugins and registered tasks.
*   **Configuration**: Leverages the `configurations` module to load its settings, including paths for plugins, tasks, and logging.
*   **Service Lifecycle**: Provides `on_startup` and `on_shutdown` hooks to manage the initialization and graceful termination of its managed services and tasks.
*   **File System Monitoring**: Uses `watchdog` to detect changes in task directories, enabling automatic registration of new tasks without requiring a full application restart.
*   **Robustness**: Employs custom error handling and transactional decorators for reliable execution of core functionalities.

*   **Dynamic Plugin Management**: The `manager` module, through its `plManager` sub-module (to be detailed later), handles the loading, reloading, and lifecycle of FastAPI plugins.
*   **Background Task Orchestration**: It discovers, registers, schedules, and executes background tasks, often defined within plugins or linked to the `backgroundtask/` directory.
*   **Internal Database**: The manager maintains its own database (configured via `manager/conf.py` and `manager/db.py`) to store metadata about active plugins and registered tasks.
*   **Configuration**: Leverages the `configurations` module to load its settings, including paths for plugins, tasks, and logging.
*   **Service Lifecycle**: Provides `on_startup` and `on_shutdown` hooks to manage the initialization and graceful termination of its managed services and tasks.
*   **File System Monitoring**: Uses `watchdog` to detect changes in task directories, enabling automatic registration of new tasks without requiring a full application restart.

---

I will now proceed with documenting the next subdirectory within `manager/`: `manager/models/`.
