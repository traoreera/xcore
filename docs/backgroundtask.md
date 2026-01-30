# Module Documentation: backgroundtask/

The `backgroundtask/` directory serves as a central location for storing or linking scheduled tasks within the `xcore` framework. It acts as a collection point for various background processes that can be executed by the system's task scheduler.

## Purpose

This directory is not intended to contain core application logic itself. Instead, it is designed to house Python scripts or modules that define specific tasks. These tasks can originate from:

*   **Plugins**: A plugin might define background jobs that are critical to its functionality.
*   **Core System**: The `xcore` framework itself might have internal maintenance or data processing tasks.

## How Tasks are Managed

Tasks are typically integrated into the `backgroundtask/` directory in one of two ways:

1.  **Direct Placement**: A task script can be placed directly within this directory.
2.  **Symbolic Linking**: More commonly, especially for tasks defined within plugins, a symbolic link is created from the plugin's task file to this directory. This allows the task to remain part of the plugin's structure while being discoverable by the central task manager.

### Using the `makefile` for Linking Tasks

The project's `makefile` provides a convenient command for creating symbolic links to tasks:

```bash
make link FROM=./plugins/your_plugin/tasks/my_task.py TO=./backgroundtask NAME=my_task.py
```

*   `FROM`: Specifies the path to the original task script (e.g., within a plugin).
*   `TO`: Specifies the destination directory, which is typically `./backgroundtask`.
*   `NAME`: The desired name for the symbolic link within `backgroundtask/`.

### Configuration in `config.json`

The behavior of the task manager, including how it interacts with the `backgroundtask/` directory, is configured in `config.json` under the `manager.tasks` section:

```json
"manager": {
    "tasks": {
        "directory": "./backgroundtask", // Specifies where the task manager looks for tasks
        "default": "./manager/plTask.py", // Default task module (if any)
        "auto_restart": true,             // Whether to auto-restart failed tasks
        "interval": 2,                    // Interval for scanning/managing tasks
        "max_retries": 3                  // Maximum retries for a failed task
    }
}
```

## Integration with the Task Scheduler

The `manager/task/taskmanager.py` (or similar components within the `manager` module) is responsible for:

*   **Discovering Tasks**: Periodically scans the `backgroundtask/` directory to identify available task scripts.
*   **Scheduling**: Integrates with `APScheduler` to schedule and execute these tasks based on their definitions (e.g., cron jobs, intervals).
*   **Monitoring**: Tracks the execution status, logs, and performance of each task.

## Development Considerations

When developing a task:

*   Ensure your task script is a valid Python module that the scheduler can import and execute.
*   Consider logging within your task to enable effective monitoring using the `make logs-tasks` commands.
*   Define the scheduling parameters (e.g., frequency, cron expression) if your task requires it, usually within the task script itself or through specific metadata.
