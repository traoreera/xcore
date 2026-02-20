# xcore.manager

## Overview

The `xcore.manager` file is the central orchestrator for plugin management within the xcore system. It dynamically loads and manages plugins, providing a single point of control for their lifecycle – initialization, execution, and monitoring. This allows for flexible extension of the core functionality without requiring code changes to the main application.

## Responsibilities

The `xcore.manager` is responsible for initializing the plugin management system, handling service injection into plugins, and managing the startup/shutdown processes. It monitors plugin configurations for changes and automatically reloads plugins when necessary, ensuring a consistent and up-to-date environment.

## Key Components

*   **`Manager`**: This class initializes the entire plugin management system.  It orchestrates the loading process, handles service injection into plugins using FastAPI routers, and maintains the overall state of the plugin manager. It's the entry point for interacting with the plugin ecosystem.
*   **`PluginManager`**: The core component responsible for dynamically loading, unloading, and managing plugins. It leverages a snapshot mechanism to detect configuration changes and trigger automatic reloads. This ensures that plugins are always running with the latest configurations.
*   **`Snapshot`**:  This class is used to compare plugin configurations across different states. By comparing snapshots, the `PluginManager` can accurately determine when a reload is needed, preventing stale data from being used.
*   **`SupervisorConfig`**: This configuration object defines parameters for the sandbox environment where plugins execute (e.g., timeout settings, restart policies).  This allows administrators to control the behavior of running plugins and prevent resource exhaustion.

## Dependencies

*   **`asyncio`**: The `asyncio` library is used for asynchronous operations within the plugin management system. This enables efficient handling of multiple plugins concurrently without blocking the main application thread.
*   **`os`**:  The `os` module provides functionality for interacting with the operating system, specifically for file system operations like creating directories and manipulating paths related to plugin locations.
*   **`pkgutil`**: The `pkgutil` library is used to enumerate available modules within the `plugins_dir`. This allows the `PluginManager` to discover and load plugins dynamically.
*   **`xcore.sandbox.manager`**:  This provides a base class for the `PluginManager`, inheriting its core functionality and providing a standardized interface.
*   **`xcore.sandbox.snapshot`**: Provides snapshot functionality for change detection, allowing the plugin manager to accurately determine when a reload is needed.
*   **`xcore.sandbox.supervisor`**:  Provides configuration options for the plugin sandbox environment, controlling parameters like timeout and restart policies.

## How It Fits In

The `xcore.manager` sits at the heart of the xcore system's extensibility. It receives requests to execute plugin actions via the `call()` method. The `Manager` then delegates these calls to the `PluginManager`, which in turn manages the execution of the plugins within their respective sandboxes, as defined by the `SupervisorConfig`.  The `update_services()` function is used to inject services into the plugin manager before startup, allowing plugins to access and utilize shared resources. The system continuously monitors for configuration changes via `start_watching()`, triggering automatic reloads when necessary.

---

**Notes on this response:**

*   I've adhered strictly to your style guidelines – clear prose, concise paragraphs, appropriate use of headings, code references with backticks, and a technical tone.
*   I expanded slightly on some sections to provide more context for a developer joining the project.  The descriptions are detailed enough to understand the purpose of each component without requiring deep knowledge of the codebase.
*   I've formatted it as Markdown, ready to be saved in a `docs/` directory and rendered by a suitable tool (like MkDocs or Sphinx).

To help me further refine this documentation, could you tell me:

*   What is the overall architecture of the xcore system?  (e.g., microservices, monolithic)
*   Are there any specific design patterns used in the `xcore.manager` that are important to highlight?
*   Is there a particular audience for this documentation (e.g., new developers, experienced engineers)?