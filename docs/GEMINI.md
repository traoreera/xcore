# xcore - Multi-Plugins Framework for FastAPI

## Project Overview

xcore is an advanced FastAPI framework designed for dynamic plugin management, scheduled task execution, and robust administration. It emphasizes modularity, hot-reloading of plugins, sandboxing for isolation, and comprehensive monitoring capabilities. Built with Python 3.10+, it leverages Poetry for dependency management, SQLAlchemy for ORM, Alembic for migrations, and Uvicorn for serving the application.

## Main Technologies

*   **Backend:** FastAPI, Python 3.10+
*   **Dependency Management:** Poetry
*   **Web Server:** Uvicorn (development), Gunicorn (production via Docker)
*   **Database:** SQLAlchemy (ORM), Alembic (migrations), supports SQLite (default), MySQL
*   **Scheduling:** APScheduler
*   **Configuration:** JSON-based (`config.json`)
*   **Authentication:** `python-jose`, `passlib` (bcrypt), `pyotp`
*   **Linting/Formatting:** Black, Isort, autoflake, autopep8, flake8
*   **Testing:** Pytest, pytest-asyncio, httpx, faker, pytest-cov

## Architecture

The core application is a FastAPI instance (`xcore.app`). It dynamically loads and manages plugins located in the `./plugins` directory, as defined in `config.json`. These plugins can expose their own FastAPI routes, which are hot-reloaded. The system also includes a task manager for scheduled or background tasks, security features like access control middleware (roles/permissions), and a comprehensive logging system. Database management is handled through SQLAlchemy and Alembic, with automatic model discovery and migration capabilities.

## Building and Running

### Prerequisites
*   Python 3.10+
*   Poetry

### Installation
```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
poetry install
```

### Running in Development Mode
```bash
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8082
# Alternatively using make:
make run-dev
```

### Running in Production Mode
```bash
# Using uvicorn (without hot-reload):
poetry run uvicorn main:app --host 0.0.0.0 --port 8081
# Alternatively using make:
make run-st
```

### Running with Docker (Development)
```bash
make docker-dev
# or directly:
sudo docker compose -f ./docker/docker-compose.dev.yml up --build
```

### Running with Docker (Production)
```bash
make docker-prod
# or directly:
sudo docker compose -f ./docker/docker-compose.prod.yml up --build -d
```

### Database Migrations
```bash
# Perform auto-migration based on model changes
poetry run python tools/auto_migrate.py

# Other migration scripts
# poetry run python tools/migrate.py
# poetry run python tools/model_discovery.py
```
*(Note: Refer to `makefile` and `tools/` directory for full migration commands.)*

### Plugin Management
```bash
# Add a new plugin (replaces PLUGIN_NAME and PLUGIN_REPO variables)
# make add-plugin PLUGIN_NAME=myplugin PLUGIN_REPO=https://github.com/user/myplugin.git

# Remove a plugin
# make rm-plugin PLUGIN_NAME=myplugin
```

## Development Conventions

*   **Code Formatting:** Uses Black, Isort, and autopep8. Automated fixing is available via `make lint-fix` or `make auto-fix`.
*   **Linting:** Flake8 is used for static analysis, can be run via `make lint-safe`.
*   **Testing:** Pytest is used for running tests. Execute with `make test`.
*   **Pre-commit Hooks:** The `pyproject.toml` and potentially a `.pre-commit-config.yaml` (not explicitly checked but common with dev dependencies) indicate use of pre-commit hooks.
*   **Logging:** Extensive logging capabilities are integrated. Use `make help` and `make logs-*` commands for various logging operations.
