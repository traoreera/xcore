# Module Documentation: loggers/

The `loggers/` module provides a centralized and configurable logging system for the `xcore` framework. It enables consistent log formatting, colored console output, and file-based logging, making it easier to monitor and debug the application's behavior.

## Files and Their Roles

*   **`loggers/__init__.py`**: (Likely empty or for package initialization).
*   **`loggers/logger_config.py`**: Contains the core logic for configuring and providing logger instances. This includes a custom formatter for colored console output and functions to set up file handlers.

## Key Concepts and Functionality

### Custom Colored Formatter (`ColoredFormatter`)

The `logger_config.py` module introduces a custom `ColoredFormatter` for console output. This formatter enhances readability by:
*   Adding **colors** to log messages based on their severity level (e.g., green for INFO, red for ERROR).
*   Including **emojis/icons** to visually denote the log level (e.g., ℹ️ for INFO, ❌ for ERROR).
*   Standardizing the log message format to include timestamp, log level, logger name, and the message content.

### Log Level Configuration

The global logging level for the application can be controlled via the `LOG_LEVEL` environment variable. If `LOG_LEVEL` is not set, the default level is `INFO`. This allows developers to dynamically adjust the verbosity of logs without modifying code.

### Flexible Logger Setup (`setup_logger`, `get_logger`)

The module provides two main functions for logger management:

*   **`setup_logger(name: str, log_file: Optional[str] = None, console: bool = True)`**:
    *   This function configures a `logging.Logger` instance with a specified `name`.
    *   It can output logs to the **console** (using `ColoredFormatter`) if `console=True`.
    *   It can also output logs to a **file** if `log_file` is provided, using a standard, non-colored formatter suitable for persistent storage and parsing.
    *   Existing handlers for the logger are cleared to prevent duplicate log entries.

*   **`get_logger(module_name: str, log_file: Optional[str] = "app.log", console: bool = True)`**:
    *   This is the primary entry point for other modules to obtain a configured logger.
    *   It automatically constructs the `log_file` path (placing it within the `./logs/` directory) and then calls `setup_logger`.
    *   The `module_name` typically corresponds to the name of the module requesting the logger, facilitating clear source identification in log outputs.

### Log File Management

Log files are typically stored in the `./logs/` directory (e.g., `app.log`, `manager.log`, `migration.log`), as configured in `config.json`. The `setup_logger` function ensures that the necessary log directory exists before writing to a file.

## Integration with Other Modules

*   **`xcore/appcfg.py`**: Initializes the main application logger (`logger`) using `get_logger`, passing logging configuration (`log_file`, `console`) from `xcfg.custom_config["logs"]`.
*   **`configurations/`**: The `config.json` file, managed by the `configurations` module, defines the specific log file names and console output settings for different parts of the application (e.g., `xcore.logs`, `manager.log`, `migration.log`).
*   **`manager/`**: The `Manager` service typically gets its own logger instance.
*   **`tools/auto_migrate.py`**: The migration scripts use a dedicated logger.
*   **`makefile`**: The extensive `make logs-*` commands leverage the structured logging by tailing, grepping, and analyzing the generated log files for debugging, monitoring, and auditing purposes.

By using this centralized logging system, developers can easily trace application flow, diagnose issues, and monitor system health.
