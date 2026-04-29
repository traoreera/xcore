# GEMINI.md - XCore Framework Context

## Project Overview
**XCore v2.1.2** is a high-performance, plugin-first orchestration framework built on top of **FastAPI**. It is designed to load, isolate, and manage modular extensions (plugins) in a secure, sandboxed environment.

### Core Architecture
- **Xcore Kernel**: The central orchestrator managing the runtime, sandbox, and communication.
- **Service Container**: Manages shared services like Databases (SQLAlchemy), Caching (Redis/Memory), and Schedulers (APScheduler).
- **Plugin Supervisor**: Handles the lifecycle (load, boot, shutdown, reload) and security of plugins.
- **Event Bus & Hooks**: Facilitates communication between the core and plugins.
- **Observability**: Integrated logging, metrics, and tracing.
- **Security**: Supports plugin signing, manifest validation, and import/resource restriction.

### Main Technologies
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Dependency Management**: Poetry / UV
- **Data Validation**: Pydantic v2
- **ORM**: SQLAlchemy 2.0
- **Task Scheduling**: APScheduler
- **CLI**: Rich-based custom CLI (`xcore`)

---

## Building and Running

### Prerequisites
- Python 3.11 or higher
- [Poetry](https://python-poetry.org/)

### Key Commands
| Task | Command | Description |
| :--- | :--- | :--- |
| **Setup** | `make install` | Install dependencies using Poetry |
| **Initialization** | `make init` | Install dependencies and start dev server |
| **Run (Dev)** | `make dev` | Run FastAPI server with auto-reload (port 8000) |
| **Run (Prod)** | `make st` | Run FastAPI server in production mode |
| **Test** | `make test` | Run the full test suite with coverage |
| **Lint & Format** | `make lint-fix` | Auto-format (Black, Isort) and fix linting |
| **Security Audit** | `make auto-security` | Run Bandit security scans |
| **Clean** | `make clean` | Remove Python cache and temporary files |
| **CLI Help** | `poetry run xcore --help` | Access the framework's CLI tools |

---

## Development Conventions

### Coding Standards
- **Formatting**: Strictly follow `black`, `isort`, and `autopep8`. Run `make lint-fix` before committing.
- **Typing**: Extensive use of Python type hints is mandatory.
- **Naming**: Follow PEP 8 (snake_case for functions/variables, PascalCase for classes).

### Plugin Structure
Plugins reside in the `plugins/` directory.
```text
plugins/my_plugin/
├── plugin.yaml      # Manifest (metadata, permissions, entry point)
├── src/
│   └── main.py      # Plugin logic
└── tests/           # Plugin-specific tests
```

### Configuration
Managed via `xcore.yaml` (or `integation.yaml`) and loaded via `xcore/configurations/loader.py`.
- **Environment Overrides**: Supports `XCORE__SECTION__KEY` environment variables.
- **Substitution**: Supports `${VAR}` in configuration files.
- **Sections**: `app`, `plugins`, `services` (databases, cache, scheduler), `observability`, `security`, `marketplace`.

### Logging & Monitoring
- Logs are written to `log/app.log`.
- Use `make logs-live` for real-time analysis.
- Detailed log categories: `make logs-auth`, `make logs-db`, `make logs-plugins`, etc.

---

## Key Directories
- `xcore/kernel/`: Core logic (runtime, sandbox, events, permissions).
- `xcore/services/`: Built-in service providers (DB, Cache, Scheduler).
- `xcore/sdk/`: Tools and base classes for plugin developers.
- `xcore/cli/`: Command-line interface implementation.
- `xcore/registry/`: Plugin discovery and versioning.
- `tests/`: Integration and unit tests.
- `doc/` & `docs-tech/`: Comprehensive project documentation.
- `docgen/`: Documentation generation pipeline.
