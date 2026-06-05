# GEMINI.md - XCore Framework Context

## Project Overview
**XCore v2.3.2** is a high-performance, plugin-first orchestration framework built on top of **FastAPI**. It is designed to load, isolate, and manage modular extensions (plugins) in a secure, sandboxed environment.

### Core Architecture
- **Xcore Kernel**: The central orchestrator managing the runtime, sandbox, and communication. Includes a C++ `scanner_core` for high-performance security scanning.
- **Service Container**: Manages shared services like Databases (SQLAlchemy 2.0), Caching (Redis/Memory), and Schedulers (APScheduler).
- **Plugin Supervisor**: Handles the lifecycle (load, boot, shutdown, reload) and security of plugins.
- **Event Bus & Hooks**: Facilitates communication between the core and plugins via an asynchronous event system.
- **Observability**: Integrated logging, metrics (Prometheus-ready), and tracing.
- **Security**: Supports plugin signing, manifest validation, and strict import/resource restriction.

### Main Technologies
- **Language**: Python 3.12+ (with C++ extensions for security)
- **Framework**: FastAPI [standard]
- **Dependency Management**: Poetry / UV
- **Data Validation**: Pydantic v2
- **ORM**: SQLAlchemy 2.0 (PostgreSQL/SQLite)
- **Task Scheduling**: APScheduler & Celery
- **CLI**: `xcoreCli` (external package)
- **SDK**: `xcoresdk` (external package)

---

## Building and Running

### Prerequisites
- Python 3.12 or higher
- [Poetry](https://python-poetry.org/) 2.0+

### Key Commands
| Task | Command | Description |
| :--- | :--- | :--- |
| **Setup** | `make install` | Install dependencies using Poetry |
| **Initialization** | `make init` | Permissions setup, install, and start dev server |
| **Run (Dev)** | `make dev` | Run FastAPI server with auto-reload (port 8000) |
| **Run (Prod)** | `make st` | Run FastAPI server in production mode |
| **Test** | `make test` | Run unit tests with Pytest |
| **Coverage** | `make test-cov` | Run tests and generate coverage reports |
| **Benchmark** | `make benchmark` | Run performance benchmarks |
| **Lint & Format** | `make lint-fix` | Auto-format (Black, Isort, Autoflake) |
| **Security Audit** | `make security` | Run Bandit security scans and check `.env` |
| **Scanner Build** | `make scanner-core` | Compile the C++ `scanner_core` extension |
| **Clean** | `make clean` | Remove Python cache and temporary files |
| **CLI** | `poetry run xcore` | Access the framework's CLI tools |

---

## Development Conventions

### Coding Standards
- **Formatting**: Strictly follow `black`, `isort`. Run `make lint-fix` before committing.
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
Managed via `xcore.yaml` (or `integration.yaml`) and loaded via `xcore/configurations/loader.py`.
- **Environment Overrides**: Supports `XCORE__SECTION__KEY` environment variables.
- **Substitution**: Supports `${VAR}` in configuration files.
- **Sections**: `app`, `plugins`, `services`, `observability`, `security`, `marketplace`.

---

## Key Directories
- `xcore/kernel/`: Core logic (runtime, sandbox, events, permissions).
- `xcore/kernel/security/`: Security implementations, including C++ `scanner_core`.
- `xcore/services/`: Built-in service providers (DB, Cache, Scheduler, Worker).
- `xcore/sdk/`: Legacy SDK components (prefer `xcoresdk` package).
- `xcore/registry/`: Plugin discovery and versioning.
- `tests/`: Integration, unit, and benchmark tests.
- `doc/`: Documentation source (MkDocs).
