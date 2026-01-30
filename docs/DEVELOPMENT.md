# DEVELOPMENT.md - Developer Guide for xcore

This guide provides in-depth information for developers working on the `xcore` project, expanding upon the `README.md` and `GEMINI.md` files.

## Table of Contents

1.  [Introduction](#introduction)
2.  [Getting Started](#getting-started)
3.  [Project Structure Overview](#project-structure-overview)
4.  [Plugin Development Guide](#plugin-development-guide)
    *   [Plugin Structure](#plugin-structure)
    *   [Plugin Metadata (`PLUGIN_INFO`)](#plugin-metadata-plugin_info)
    *   [Registering a Plugin](#registering-a-plugin)
    *   [Hot-Reloading and Dynamic Behavior](#hot-reloading-and-dynamic-behavior)
    *   [Sandbox Considerations](#sandbox-considerations)
5.  [Task Scheduling](#task-scheduling)
6.  [Configuration Management](#configuration-management)
7.  [Database Management and Migrations](#database-management-and-migrations)
8.  [API Documentation](#api-documentation)
9.  [Logging and Monitoring](#logging-and-monitoring)
10. [Code Style and Quality](#code-style-and-quality)
11. [Deployment Considerations](#deployment-considerations)

---

## 1. Introduction

`xcore` is a powerful FastAPI framework designed to facilitate dynamic plugin management, scheduled task execution, and robust administrative features. This document aims to guide developers through the intricacies of extending, maintaining, and understanding the `xcore` ecosystem.

---

## 2. Getting Started

For initial setup, installation, and basic running instructions, please refer to the main [`README.md`](README.md) file. It covers the prerequisites, how to install dependencies using Poetry, and how to run the application in development or production modes.

---

## 3. Project Structure Overview

The `xcore` project is organized into several key directories, each serving a specific purpose:

*   **`.github/`**: Contains GitHub Actions workflows, such as `pylint.yml` for CI/CD.
*   **`admin/`**: Modules related to administrative functionalities, including routes, schemas, and services for managing the system.
*   **`alembic/`**: Alembic configuration and migration scripts for database schema management.
*   **`auth/`**: Authentication and authorization modules, handling user creation, login, token management, and root user initialization.
*   **`backgroundtask/`**: Directory where scheduled tasks defined by plugins or the core system are linked or placed.
*   **`cache/`**: Caching mechanisms, potentially using Redis.
*   **`configurations/`**: Core configuration loading and management logic, including `base.py`, `core.py`, and `manager.py`. This is where `config.json` is processed.
*   **`database/`**: Database connection setup and session management using SQLAlchemy.
*   **`loggers/`**: Centralized logging configuration.
*   **`manager/`**: The core plugin and task management framework.
    *   **`manager/plManager/`**: Contains the logic for loading, reloading, installing, and validating plugins (`loader.py`, `reloader.py`, `installer.py`, `validator.py`).
    *   **`manager/crud/`**: CRUD operations for manager-related entities (e.g., plugins, tasks).
    *   **`manager/models/`**: SQLAlchemy models for internal manager data.
    *   **`manager/routes/`**: API routes exposed by the manager itself (e.g., for task management).
    *   **`manager/schemas/`**: Pydantic schemas for data validation within the manager.
    *   **`manager/task/`**: Logic related to task execution and scheduling.
*   **`middleware/`**: Custom FastAPI middleware, such as `access_control_Middleware.py` for role-based access control.
*   **`otpprovider/`**: Modules for One-Time Password (OTP) generation and verification.
*   **`plugins/`**: The main directory where dynamic plugins are expected to reside. Each sub-directory within `plugins/` represents a separate plugin.
*   **`security/`**: Security-related utilities, including password hashing (`hash.py`) and token management (`token.py`).
*   **`tools/`**: Command-line tools and scripts for project maintenance, such as `auto_migrate.py`, `migrate.py`, and `model_discovery.py`.
*   **`xcore/`**: The main application package.
    *   **`xcore/__init__.py`**: Initializes the main `FastAPI` application instance.
    *   **`xcore/appcfg.py`**: Loads the main application configuration (`config.json`).
    *   **`xcore/manage.py`**: Initializes the `Manager` service, linking the core app with the plugin system.
    *   **`xcore/view.py`**: Integrates routers from other core modules into the main FastAPI application.
*   **`config.json`**: The central configuration file for the entire `xcore` framework.
*   **`main.py`**: The entry point for running the FastAPI application.
*   **`pyproject.toml`**: Project metadata and dependency management using Poetry.
*   **`makefile`**: Contains various commands for development, deployment, and administrative tasks.

---

## 4. Plugin Development Guide

The core strength of `xcore` lies in its dynamic plugin system. This section guides you through creating and integrating your own plugins.

### Plugin Structure

A typical plugin should have the following minimal structure within the `plugins/` directory:

```
plugins/
└── your_plugin_name/
    ├── __init__.py
    ├── run.py          # Plugin entry point (contains PLUGIN_INFO and router)
    └── router.py       # (Optional) Additional routes for your plugin
    └── config.yaml     # (Optional) Plugin-specific configuration
```

### Plugin Metadata (`PLUGIN_INFO`)

Your plugin's main entry file (`run.py`) **must** define a `PLUGIN_INFO` dictionary and expose a FastAPI `APIRouter` instance.

**Example `plugins/your_plugin_name/run.py`:**

```python
from fastapi import APIRouter, Request, Depends
# from your_plugin_name.dependencies import get_db_session # Example dependency

PLUGIN_INFO = {
    "version": "1.0.0",
    "author": "Your Name",
    "Api_prefix": "/app/your_plugin_name", # Base path for your plugin's API
    "tag_for_identified": ["your_plugin_name"], # Tags for OpenAPI documentation
    "description": "A brief description of your plugin.",
    # Add other metadata as needed, e.g., 'dependencies', 'tasks'
}

router = APIRouter(
    prefix=PLUGIN_INFO["Api_prefix"],
    tags=PLUGIN_INFO["tag_for_identified"],
)

# Example route within your plugin
@router.get("/")
async def read_root_plugin(request: Request):
    return {"message": f"Hello from {PLUGIN_INFO['tag_for_identified'][0]} plugin!"}

# Example with a custom class to hold logic
class Plugin:
    def __init__(self):
        self.counter = 0

    @router.get("/count")
    async def get_count(self):
        self.counter += 1
        return {"current_count": self.counter}

# If your plugin has methods or logic that need to be exposed,
# you can instantiate your plugin class here or define them directly
# as functions with the @router decorator.
# For more complex plugins, consider separating logic into service files.
```

### Registering a Plugin

`xcore` includes a `makefile` target to help you add new plugins by cloning them from a Git repository:

```bash
# Example: Add a plugin named 'myawesomeplugin' from a GitHub repository
make add-plugin PLUGIN_NAME=myawesomeplugin PLUGIN_REPO=https://github.com/yourusername/myawesomeplugin.git

# To remove a plugin:
make rm-plugin PLUGIN_NAME=myawesomeplugin
```

The `add-plugin` command clones the repository into the `plugins/` directory. The `Manager` service will then discover and load it dynamically based on the `plugins.directory` and `plugins.entry_point` settings in `config.json`.

### Hot-Reloading and Dynamic Behavior

`xcore` supports hot-reloading of plugins. When changes are detected in a plugin's files, the `Manager` will attempt to unload the old version and load the new one without restarting the entire FastAPI application. This feature is controlled by the `manager.plugins.interval` setting in `config.json`.

**Important:** Due to Python's module caching mechanisms, extensive changes might sometimes require a full application restart for all changes to take effect perfectly, especially for changes in `__init__.py` or deep module dependencies.

### Sandbox Considerations

`xcore` is designed to run plugins in a sandboxed environment (though the implementation details might vary). This means plugins should be developed with the understanding that their access to system resources (CPU, memory, execution time) might be limited to prevent a misbehaving plugin from impacting the stability of the entire system. Refer to the `security` section of the `README.md` and `config.json` for details on sandboxing.

---

## 5. Task Scheduling

The framework integrates a scheduler (powered by `APScheduler`) to manage periodic or one-off tasks. Tasks can be defined within your plugins or as standalone scripts that the `Manager` can discover.

*   **Defining Tasks:** Tasks are typically Python scripts located in the `backgroundtask/` directory. You can link your plugin's tasks to this directory using `make link`.
*   **Configuration:** The `manager.tasks` section in `config.json` defines the task directory, auto-restart behavior, intervals, and max retries.
*   **Monitoring:** The `make logs-tasks` command is useful for monitoring the execution and status of scheduled tasks.

---

## 6. Configuration Management

The central configuration for `xcore` and its core modules is managed via `config.json`.

*   **Structure:** The `config.json` is structured hierarchically, with sections for `manager`, `secure`, `migration`, `xcore`, and `redis`.
*   **Loading:** The `xcore.appcfg.py` module loads this configuration into the `xcfg` object, which is then accessible throughout the application.
*   **Overrides:** Many settings within `config.json` can often be overridden by environment variables (e.g., `DATABASE_URL`, `REDIS_HOST`). Consult the `configurations/` directory for the exact precedence rules and available environment variables.
*   **Middleware Access Rules:** The `xcore.middleware.ACCESS_RULES` section in `config.json` is critical for defining granular access control policies based on roles, permissions, and HTTP methods for various API endpoints.

---

## 7. Database Management and Migrations

`xcore` uses SQLAlchemy as its ORM and Alembic for database schema migrations.

*   **Database URL:** Configured in `config.json` under `migration.url` and `xcore.data.url`. These can typically be overridden by environment variables (e.g., `DATABASE_URL`).
*   **Models:** SQLAlchemy models are defined in the `models/` subdirectories of various modules (e.g., `auth/models.py`, `manager/models/`).
*   **Auto-Migration:** The `tools/auto_migrate.py` script, orchestrated by `make auto_migrate`, facilitates automatic generation and application of migrations based on changes detected in your SQLAlchemy models.
    ```bash
    make auto_migrate
    # Equivalent to: poetry run python tools/auto_migrate.py
    ```
*   **Model Discovery:** The system automatically discovers models from specified directories (e.g., `auth`, `manager/models/`, `admin/`, `otpProvider`, and plugins) as defined in `config.json` (`migration.automigration.models` and `migration.automigration.plugins`).
*   **Backup:** Migrations can be configured to create automatic backups of the database before applying changes, as defined in `config.json` (`migration.backup`).

---

## 8. API Documentation

FastAPI provides excellent built-in interactive API documentation through OpenAPI (Swagger UI) and ReDoc.

*   **Swagger UI:** Accessible at `/docs` when your application is running. This provides an interactive interface to explore and test your API endpoints, including those exposed by loaded plugins.
*   **ReDoc:** Accessible at `/redoc`, offering an alternative, more concise API documentation view.
*   **Plugin Integration:** When plugins expose their routes via `APIRouter`, their endpoints are automatically integrated into the main application's OpenAPI documentation. Ensure your `PLUGIN_INFO` tags are descriptive.

---

## 9. Logging and Monitoring

`xcore` incorporates a comprehensive logging system. The `makefile` provides a wide array of commands for viewing, filtering, and analyzing application logs, which are typically directed to `logs/dev.log` or `logs/app.log` (as configured in `config.json`).

*   **Basic Log Viewing:**
    *   `make logs`: View the last 100 lines of the main log file.
    *   `make logs-live`: Stream logs in real-time (`tail -f`).
*   **Filtering by Level:** `make logs-debug`, `make logs-info`, `make logs-warning`, `make logs-error`, `make logs-critical`.
*   **Filtering by Context:** `make logs-auth` (authentication), `make logs-db` (database), `make logs-api` (API routes), `make logs-plugins` (plugins), `make logs-tasks` (tasks), `make logs-email` (emails).
*   **Advanced Analysis:**
    *   `make logs-stats`: View log statistics (total lines, counts per level).
    *   `make logs-search TERM="your_keyword"`: Search logs for a specific term.
    *   `make logs-errors-and-warnings`: Combine error and warning logs.
    *   `make logs-security-audit`, `make logs-performance-check`, `make logs-startup-analysis`, `make logs-user-activity`, `make logs-api-monitoring`, `make logs-database-health`, `make logs-plugins-status`, `make logs-email-monitoring`: Specialized audit and monitoring reports.
    *   `make logs-full-report`: Comprehensive system health report.
    *   `make logs-dashboard`: Real-time log dashboard.
*   **Log Maintenance:** `make logs-clean`: Clears the current log file and creates a backup.

---

## 10. Code Style and Quality

`xcore` adheres to modern Python code style and quality practices.

*   **Formatting:** The project uses `black` for uncompromising code formatting, `isort` for sorting imports, and `autopep8` for PEP 8 compliance.
*   **Linting:** `flake8` is used for static code analysis to catch common errors and style violations.
*   **Automated Fixes:**
    ```bash
    make lint-fix # or make auto-fix
    ```
    This command automatically applies `autopep8`, `isort`, `black`, and `autoflake` (for removing unused variables) to the codebase.
*   **Testing:** Unit and integration tests are crucial.
    ```bash
    make test
    ```
    This command runs `pytest` with coverage reporting. Developers are encouraged to write tests for new features and bug fixes.
*   **Security Checks:** `make security-check` performs basic checks like verifying `.env` is not committed and scanning for hardcoded passwords.

---

## 11. Deployment Considerations

`xcore` supports deployment via Docker, with separate configurations for development and production environments.

*   **Docker Compose:**
    *   `docker/docker-compose.dev.yml`: For development, typically includes hot-reloading and debugging tools.
    *   `docker/docker-compose.prod.yml`: For production, optimized for performance and stability (e.g., using Gunicorn).
*   **Docker Commands:**
    *   `make docker-dev`: Build and run the development Docker containers.
    *   `make docker-prod`: Build and run the production Docker containers (in detached mode).
    *   `make docker-stop`: Stop Docker containers.
    *   `make docker-clean`: Stop, remove containers/volumes, and prune the Docker system.
*   **External Scripts:** The `makefile` also references external shell scripts in the `./script/` directory (e.g., `install.sh`, `uninstall.sh`, `cmd.sh`) for more complex deployment and server management tasks. Consult these scripts for their specific functionalities.
*   **Nginx Configuration:** `make repaire-ng` suggests interaction with Nginx for reverse proxying or serving the application, which is common for production deployments.

This `DEVELOPMENT.md` aims to be a living document. Contributions and improvements are welcome.
