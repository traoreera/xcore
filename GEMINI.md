# GEMINI.md - XCore Framework Context

This file provides a comprehensive overview of the XCore project to guide development and maintenance.

## Project Overview

**XCore** is a high-performance, plugin-first orchestration framework built on top of **FastAPI**. It is designed to load, isolate, and manage modular extensions (plugins) in a secure, sandboxed environment.

### Core Architecture
- **Xcore Kernel**: The central orchestrator managing sub-systems.
- **Service Container**: Manages shared services like Databases (SQLAlchemy), Caching (Redis/Memory), and Schedulers (APScheduler).
- **Plugin Supervisor**: Handles the lifecycle (load, boot, shutdown, reload) of plugins.
- **Event Bus & Hooks**: Facilitates communication between the core and plugins via events and hooks.
- **Observability**: Integrated logging, metrics (Prometheus/Memory), and tracing (OpenTelemetry).
- **Security**: Supports plugin signing, verification, and sandboxed execution to restrict resource access.

### Main Technologies
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Dependency Management**: Poetry
- **Data Validation**: Pydantic v2
- **ORM/Database**: SQLAlchemy 2.0, Alembic
- **Task Scheduling**: APScheduler
- **CLI**: Custom CLI built with Rich

## Building and Running

The project uses a `Makefile` to simplify common development tasks.

### Prerequisites
- Python 3.11 or higher
- [Poetry](https://python-poetry.org/docs/#installation)

### Key Commands
| Task | Command | Description |
| :--- | :--- | :--- |
| **Setup** | `make install` | Install dependencies using Poetry |
| **Initialization** | `make init` | Install dependencies and start dev server |
| **Run (Dev)** | `make dev` | Run FastAPI server with auto-reload (port 8000) |
| **Run (Prod)** | `make st` | Run FastAPI server in production mode |
| **Test** | `make test` | Run the full test suite with coverage |
| **Lint & Format** | `make lint-fix` | Auto-format (Black, Isort) and fix linting (Autopep8, Autoflake) |
| **Security Audit** | `make auto-security` | Run Bandit security scans |
| **Clean** | `make clean` | Remove Python cache and temporary files |
| **CLI Help** | `poetry run xcore --help` | Access the framework's CLI tools |

## Development Conventions

### Coding Standards
- **Formatting**: Strictly follow `black` and `isort`. Run `make lint-fix` before committing.
- **Typing**: Use Python type hints extensively.
- **Naming**: Follow PEP 8 (snake_case for functions/variables, PascalCase for classes).

### Plugin Structure
Plugins should reside in the `plugins/` directory (created during development).
```text
plugins/my_plugin/
├── plugin.yaml      # Manifest (metadata & entry point)
├── src/
│   └── main.py      # Entry point (inherits from BasePlugin or TrustedBase)
└── tests/           # Plugin-specific tests
```

### Configuration
Configuration is managed via `xcore.yaml` and loaded through `xcore/configurations/loader.py`.
- **App**: Environment, debug mode, secret keys.
- **Plugins**: Directory path, execution mode settings.
- **Services**: Database URLs, cache backend, scheduler settings.
- **Observability**: Logging levels, metrics/tracing backends.

### Logging & Monitoring
- Logs are written to `log/app.log` by default.
- Use the numerous `make logs-*` targets (e.g., `make logs-live`, `make logs-error`, `make logs-stats`) for analysis.
- **XCore Dashboard**: Access a real-time web dashboard at `/plugin/ipc/dashboard` (default prefix) to monitor plugins, event flows, live logs, and system health.

## Key Directories
- `xcore/kernel/`: Core logic (runtime, sandbox, events, permissions).
- `xcore/services/`: Built-in service providers (DB, Cache, etc.).
- `xcore/sdk/`: Tools and decorators for plugin developers.
- `xcore/cli/`: Command-line interface implementation.
- `xcore/registry/`: Plugin discovery and versioning.
- `tests/`: Integration and unit tests.
- `doc/`: Project documentation (MkDocs/Sphinx).
