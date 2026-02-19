# GEMINI Project Analysis: xcore

This document provides a comprehensive overview of the `xcore` project, its architecture, and development workflows, intended to be used as a quick-start guide and context for development.

## 1. Project Overview

**xcore** is a sophisticated, plugin-driven framework built on top of **FastAPI**. Its primary purpose is to provide a stable core system that can be dynamically extended with sandboxed plugins.

Key features include:
*   **Dynamic Plugin Management**: Plugins can be loaded, reloaded, and managed at runtime without server restarts.
*   **Service Integration**: A centralized `Integration` layer manages access to external services like databases (using SQLAlchemy), caches (Redis), and more, based on a declarative YAML configuration (`integration.yaml`).
*   **Sandboxing**: Plugins are executed in isolated environments to control resource usage (CPU, memory) and prevent crashes from affecting the main application.
*   **Task Scheduling**: An integrated scheduler (`apscheduler`) allows plugins to define and run background tasks.
*   **Administration & Monitoring**: The framework exposes API endpoints for monitoring the status of the core application, services, and loaded plugins.

### Core Technologies
*   **Backend**: Python 3.11+ with FastAPI
*   **Dependency Management**: Poetry
*   **Database**: SQLAlchemy with Alembic for migrations
*   **Web Server**: Uvicorn
*   **Containerization**: Docker and Docker Compose
*   **Task Scheduling**: APScheduler
*   **Tooling**: A comprehensive `Makefile` orchestrates most development tasks.

## 2. Building and Running

The project uses a `Makefile` that simplifies most common operations.

### Initial Setup
1.  **Prerequisites**: Ensure you have [Poetry](https://python-poetry.org/docs/#installation) installed.
2.  **Install Dependencies**: This command installs all required Python packages defined in `pyproject.toml`.
    ```bash
    make install
    ```

### Running the Application
*   **Development Mode**: To run the server with live auto-reloading for code changes. The application will be available at `http://0.0.0.0:8082`.
    ```bash
    make run-dev
    ```

*   **Production-like Mode**: To run the server in a static mode, similar to a production environment.
    ```bash
    make run-st
    ```

### Running with Docker
*   **Development Container**: Build and run the application within a Docker container that supports auto-reload.
    ```bash
    make docker-dev
    ```

*   **Production Container**: Build and run the application using a production-ready setup with Gunicorn.
    ```bash
    make docker-prod
    ```

### Database Migrations
The project uses `alembic` for database migrations. The migration scripts are defined in `pyproject.toml` and can be run with `poetry run`.

*   **To run the main migration script**:
    ```bash
    poetry run migrate
    ```
*   **To auto-generate a migration (if available)**:
    ```bash
    poetry run auto_migrate
    ```

## 3. Development Conventions

### Code Style and Formatting
The project enforces a consistent code style using a suite of tools.
*   **Tools**: `black`, `isort`, `flake8`, `autopep8`.
*   **Automatic Formatting**: To automatically format all project files according to the defined style, run:
    ```bash
    make lint-fix
    ```
    This command should be run before committing changes.

### Testing
Tests are written using `pytest`.
*   **To run the test suite**:
    ```bash
    make test
    ```

### Plugin Management
The framework is built around plugins, which are located in the `plugins/` directory. The `Makefile` provides helpers to manage them.

*   **Adding a Plugin**: To clone a plugin from a git repository into the `plugins/` directory:
    ```bash
    make add-plugin PLUGIN_NAME=my-plugin-name PLUGIN_REPO=https://github.com/user/repo.git
    ```

*   **Removing a Plugin**: To delete a plugin from the `plugins/` directory:
    ```bash
    make rm-plugin PLUGIN_NAME=my-plugin-name
    ```

### Core Architecture
The main application logic is initialized in `app.py`. The architecture is composed of three main parts:
1.  **`Integration` (`integration.yaml`)**: This component is responsible for initializing and managing all external services (e.g., database connections, cache clients). It provides a service registry that other parts of the application can consume.
2.  **`Manager` (`xcore/manager.py`)**: This is the engine of the plugin system. It discovers plugins in the `plugins/` directory, loads them, injects the services from the `Integration` layer, and manages their lifecycle.
3.  **`FastAPI App` (`app.py`)**: This is the web layer that ties everything together. It uses a `lifespan` context manager to orchestrate the startup (initializing services, starting the plugin manager) and shutdown sequences.
