# Module Documentation: xcore/

The `xcore/` directory represents the core application package of the framework. It ties together various modules, initializes the FastAPI application, handles global configurations, and orchestrates the application's lifecycle events.

## Files and Their Roles

*   **`xcore/__init__.py`**:
    *   Initializes the main FastAPI application instance (`app`), setting its `title` and `version`. This `app` object is then imported and used throughout the framework.
*   **`xcore/appcfg.py`**:
    *   Responsible for loading the core application configuration. It instantiates `configurations.core.Xcorecfg` (as `xcfg`), which parses the `xcore` section of `config.json`.
    *   It also initializes the main application logger using `loggers.logger_config.get_logger`, based on the settings from `xcfg`.
*   **`xcore/events.py`**:
    *   Defines the `startup` and `shutdown` event handlers for the FastAPI application.
    *   **`startup_event()`**: Executes critical initialization tasks at application startup, including:
        *   Initializing the root administrator user (`admin.service.init_root_admin`).
        *   Loading and running all dynamic plugins (`manager.run_plugins()`).
        *   Starting background tasks (`manager.runtimer.on_startup()`).
    *   **`shutdown_event()`**: Handles graceful shutdown, stopping the plugin watcher (`manager.stop_watching()`), shutting down background tasks (`manager.runtimer.on_shutdown()`), and closing manager-related database connections (`manager.close_db()`).
*   **`xcore/manage.py`**:
    *   Instantiates and configures the `Manager` service (from `manager.plManager.manager.Manager`). This is the central orchestrator for plugin management, linking the core FastAPI app with the dynamic plugin system.
    *   It sets up the `Loader` and `Snapshot` configurations for plugin discovery and change detection.
*   **`xcore/middleware.py`**:
    *   Configures global FastAPI middleware for the application.
    *   Includes a custom middleware (`add_process_time_header`) that measures and logs the processing time for each request and adds an `X-Process-Time` header to responses.
    *   Adds `CORSMiddleware` (Cross-Origin Resource Sharing) to handle cross-domain requests, specifying allowed origins, credentials, methods, and headers.
    *   **Note**: The `origins` list for `CORSMiddleware` is hardcoded here, which typically should be managed through `config.json` or environment variables for flexibility in different deployment environments.
*   **`xcore/view.py`**:
    *   Integrates `APIRouter` instances from various core modules (e.g., `admin.routes`, `auth.routes`, `manager.routes.task`, `otpprovider.routes`) into the main `xcore` FastAPI application.
    *   It ensures that the API endpoints defined in these modules are accessible through the main application.
    *   Also includes an example `/device-info` endpoint that parses the User-Agent header for client device information.

## Subdirectories Overview

### `xcore/containers/`

*   Contains only an `__init__.py` file. This directory appears to be a placeholder or reserved for future implementation of dependency injection containers or other service locator patterns within the `xcore` core. Currently, it does not contain active functionality.

## Key Concepts and Functionality

### Application Initialization

The `xcore` module is responsible for the fundamental setup of the FastAPI application. `xcore/__init__.py` creates the main `FastAPI` instance, and `xcore/appcfg.py` loads the global configuration (`config.json`), making settings available throughout the application.

### Lifecycle Management

`xcore/events.py` defines critical startup and shutdown hooks, ensuring that essential services (root admin, plugins, background tasks) are properly initialized and gracefully terminated.

### Global Middleware

`xcore/middleware.py` implements global middleware that applies to all incoming requests, handling concerns like request processing time logging and CORS.

### Route Aggregation

`xcore/view.py` acts as a central point for consolidating and including API routes from various sub-modules, presenting a unified API surface for the application.

### Plugin System Integration

The `xcore` module plays a pivotal role in integrating the dynamic plugin system by instantiating the `Manager` in `xcore/manage.py` and orchestrating its startup/shutdown in `xcore/events.py`.
