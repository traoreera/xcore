# Module Documentation: plugins/

The `plugins/` directory is a special module within the `xcore` framework. It serves as the designated location for all dynamic plugins that extend the application's functionality. Unlike other modules that contain core logic, `plugins/` acts as a container for independently developed and managed modular components.

## Purpose

The primary purpose of the `plugins/` directory is to enable the hot-reloading and dynamic integration of new features, APIs, and background tasks into the `xcore` application without requiring a full application restart. Each subdirectory within `plugins/` represents a distinct plugin.

## Plugin Structure and Expectations

A well-structured plugin should adhere to the following conventions to be properly discovered, loaded, and managed by the `xcore` plugin manager (`manager/plManager/`):

```
plugins/
└── your_plugin_name/
    ├── __init__.py           # Package initializer
    ├── run.py                # Plugin's main entry point (required)
    ├── router.py             # (Optional) FastAPI APIRouter for plugin's API endpoints
    ├── models.py             # (Optional) SQLAlchemy models specific to the plugin
    ├── schemas.py            # (Optional) Pydantic schemas for API data validation
    ├── service.py            # (Optional) Business logic for the plugin
    ├── tasks/                # (Optional) Directory for background task definitions
    │   └── my_task.py
    └── plugin.json           # (Required for dependency management) Plugin metadata and installation status
    └── pyproject.toml        # (Optional) For plugin-specific Poetry dependencies
```

### Key Plugin Files

*   **`run.py` (Main Entry Point)**:
    *   This file is crucial. It must define a dictionary named `PLUGIN_INFO` containing essential metadata about the plugin (version, author, API prefix, tags).
    *   It should also typically define a `FastAPI.APIRouter` instance (e.g., `router`) that will be included in the main `xcore` application.
    *   It may contain a `Plugin` class or `service_main` function if the plugin provides long-running services or asynchronous tasks.

    **Example `PLUGIN_INFO` structure from `plugins/LibraryHub/run.py` (hypothetical):**
    ```python
    from fastapi import APIRouter

    PLUGIN_INFO = {
        "version": "1.0.0",
        "author": "HuntersX",
        "Api_prefix": "/app/library",
        "tag_for_identified": ["LibraryHub"],
        "description": "Manages a collection of books and authors."
    }

    router = APIRouter(prefix=PLUGIN_INFO["Api_prefix"], tags=PLUGIN_INFO["tag_for_identified"])

    @router.get("/")
    async def read_root():
        return {"message": "Welcome to LibraryHub"}
    ```

*   **`plugin.json` (Plugin Metadata & Dependencies)**:
    *   This file provides additional metadata and is used by the `xcore` `manager.plManager.loader` to manage plugin lifecycle and dependencies.
    *   It informs the system about the plugin's name, version, author, and crucially, its installation status for `poetry` dependencies.

    **Example `plugins/LibraryHub/plugin.json`:**
    ```json
    {
        "name": "LibraryHub",
        "version": "1.0.0",
        "author": "HuntersX",
        "active": true,
        "async": true,
        "requirements": {
            "isIstalled": true
        }
    }
    ```
    *   The `"requirements": {"isIstalled": true}` flag tells the `xcore` manager whether the plugin's `poetry` dependencies have been installed. If `false`, the `manager.plManager.installer.py` will attempt to run `poetry install` for the plugin.

*   **`pyproject.toml` (Plugin-Specific Dependencies)**:
    *   If a plugin requires external Python packages that are not part of the `xcore` core environment, it should define its own `pyproject.toml` file.
    *   The `manager.plManager.installer.py` uses this file to install these dependencies into an isolated environment for the plugin.

## Plugin Lifecycle and Integration

1.  **Discovery**: The `manager.plManager.loader` scans the `plugins/` directory for subdirectories containing `run.py` and `plugin.json`.
2.  **Installation**: If `plugin.json` indicates `requirements.isIstalled: false`, the `Installer` component attempts to install the plugin's `poetry` dependencies.
3.  **Validation**: The `manager.plManager.validator` checks if the plugin adheres to the required structure (e.g., `PLUGIN_INFO` presence).
4.  **Loading**: Valid plugins are dynamically imported into `xcore`.
5.  **FastAPI Integration**: The `loader` dynamically attaches the plugin's `APIRouter` (if defined in `run.py`) to the main `xcore` FastAPI application.
6.  **Hot-Reloading**: Changes within a plugin's files are detected by `manager.plManager.snapshot.py`, triggering a hot-reload of the plugin without restarting the entire application, maintaining the main FastAPI instance.
7.  **Task Management**: Plugins can define background tasks that are picked up and scheduled by the `manager.task.taskmanager` (possibly linked to `backgroundtask/`).

## Example Plugin: `LibraryHub`

The `plugins/LibraryHub/` directory serves as an example plugin, demonstrating the structure and files expected from a `xcore` plugin. It likely provides API endpoints and/or background services for managing a library system. Examining its `run.py` and other internal files will provide a concrete illustration of plugin development.

## Development Considerations

*   **Isolation**: Develop plugins as self-contained units.
*   **Dependencies**: Manage plugin-specific dependencies in `pyproject.toml` and ensure `plugin.json` reflects their installation status.
*   **API Prefix**: Use `PLUGIN_INFO["Api_prefix"]` to ensure unique routing paths for your plugin's endpoints.
*   **Logging**: Use `xcore`'s logging utilities for consistent log output.
*   **Error Handling**: Implement robust error handling within your plugin's logic.
*   **Testing**: Write tests for your plugin's functionality.
