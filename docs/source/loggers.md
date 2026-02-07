# loggers - Logging Configuration Module

## Overview

The `loggers` module provides standardized, colorized logging across the application. It supports console output with colors and file output with rotation.

## Module Structure

```
loggers/
├── __init__.py          # Module exports
└── logger_config.py     # Colored logging setup
```

## Core Components

### Logger Configuration

```python
# logger_config.py

import logging
import colorlog
from logging.handlers import RotatingFileHandler
from configurations import Xcorecfg

# Log level colors
LOG_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white',
}

# Formatter for console (with colors)
CONSOLE_FORMAT = (
    '%(log_color)s%(asctime)s%(reset)s | '
    '%(log_color)s%(levelname)-8s%(reset)s | '
    '%(cyan)s%(name)s%(reset)s | '
    '%(message)s'
)

# Formatter for files (without colors)
FILE_FORMAT = (
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)

def setup_logging(
    log_level: str = "INFO",
    log_file: str = None,
    max_bytes: int = 10*1024*1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup colored logging.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging
        max_bytes: Max file size before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance
    """
```

## Log Levels

| Level | Numeric Value | Usage |
|-------|---------------|-------|
| DEBUG | 10 | Detailed diagnostic information |
| INFO | 20 | General information |
| WARNING | 30 | Something unexpected happened |
| ERROR | 40 | Serious problem, functionality affected |
| CRITICAL | 50 | Program may be unable to continue |

## Usage Examples

### Basic Logging

```python
from loggers import get_logger

# Get logger for current module
logger = get_logger(__name__)

# Log messages
logger.debug("Debug information")
logger.info("Application started")
logger.warning("This is a warning")
logger.error("An error occurred")
logger.critical("Critical failure!")
```

### Module-Specific Loggers

```python
# In auth/models.py
from loggers import get_logger

logger = get_logger("auth.models")

class User:
    def __init__(self):
        logger.debug(f"Creating user instance")
```

```python
# In manager/plManager/loader.py
from loggers import get_logger

logger = get_logger("manager.loader")

class PluginLoader:
    def load(self, plugin_id: str):
        logger.info(f"Loading plugin: {plugin_id}")
        try:
            # Loading logic
            logger.debug(f"Plugin {plugin_id} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
```

### Configuration-Based Setup

```python
from loggers.logger_config import setup_logging
from configurations import Xcorecfg

config = Xcorecfg.from_file("config.json")

# Setup with configuration
logger = setup_logging(
    log_level=config.log_level,
    log_file="logs/app.log",
    max_bytes=10*1024*1024,  # 10MB
    backup_count=5
)
```

### File Logging

```python
from loggers.logger_config import setup_logging

# Enable file logging
logger = setup_logging(
    log_level="INFO",
    log_file="logs/application.log",
    max_bytes=5*1024*1024,  # 5MB per file
    backup_count=10         # Keep 10 backup files
)

# Logs will be written to both console and file
logger.info("This appears in console and file")
```

### Custom Formatting

```python
import logging
import colorlog

# Create custom formatter
def create_custom_formatter():
    return colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s | %(name)s [%(levelname)s]%(reset)s: %(message)s',
        log_colors={
            'DEBUG': 'blue',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )

# Apply to handler
handler = logging.StreamHandler()
handler.setFormatter(create_custom_formatter())

logger = logging.getLogger("custom")
logger.addHandler(handler)
```

## Console Output

Example colored console output:

```
2024-01-15 10:30:45 | INFO     | xcore.app | Application starting
2024-01-15 10:30:45 | DEBUG    | xcore.config | Loading configuration from config.json
2024-01-15 10:30:46 | INFO     | manager.loader | Loading 3 plugins
2024-01-15 10:30:46 | WARNING  | auth.service | Token expiring soon
2024-01-15 10:30:47 | ERROR    | cache.manager | Redis connection failed
2024-01-15 10:30:47 | CRITICAL | database.db | Database connection lost
```

## Log File Format

File output (without colors):

```
2024-01-15 10:30:45 | INFO     | xcore.app | Application starting
2024-01-15 10:30:45 | DEBUG    | xcore.config | Loading configuration from config.json
2024-01-15 10:30:46 | INFO     | manager.loader | Loading 3 plugins
```

## Advanced Usage

### Structured Logging

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": f"{record.filename}:{record.lineno}"
        }
        return json.dumps(log_data)

# Use JSON formatter
handler = logging.FileHandler("logs/app.json")
handler.setFormatter(JSONFormatter())
```

### Contextual Logging

```python
import logging
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar('request_id', default='')

class ContextFilter(logging.Filter):
    """Add contextual information to log records"""

    def filter(self, record):
        record.request_id = request_id.get()
        return True

# Add filter to logger
logger = logging.getLogger("app")
logger.addFilter(ContextFilter())

# Use in formatter
formatter = logging.Formatter(
    '%(asctime)s | %(request_id)s | %(levelname)s | %(message)s'
)
```

### Exception Logging

```python
from loggers import get_logger

logger = get_logger(__name__)

def risky_operation():
    try:
        # Some operation
        result = 1 / 0
    except Exception:
        # Log exception with traceback
        logger.exception("Operation failed")
        # Equivalent to:
        # logger.error("Operation failed", exc_info=True)
```

### Log Rotation

```python
from logging.handlers import TimedRotatingFileHandler

# Rotate daily
handler = TimedRotatingFileHandler(
    "logs/app.log",
    when="midnight",
    interval=1,
    backupCount=30  # Keep 30 days
)

# Rotate on size
handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=10
)
```

### Silent Mode

```python
from loggers.logger_config import setup_logging

# Disable logging
logger = setup_logging(log_level="CRITICAL")

# Or completely
logging.disable(logging.CRITICAL)
```

## Configuration

Configuration in `config.json`:

```json
{
  "loggers": {
    "log_level": "INFO",
    "log_file": "logs/app.log",
    "max_bytes": 10485760,
    "backup_count": 5,
    "enable_colors": true,
    "enable_file": true
  }
}
```

### Environment Variables

```bash
export LOG_LEVEL=DEBUG
export LOG_FILE=logs/app.log
export LOG_FORMAT=colored  # or plain, json
```

## Best Practices

### 1. Use Module-Level Loggers

```python
# Good - module-level logger
import logging
logger = logging.getLogger(__name__)

def my_function():
    logger.info("Doing something")

# Bad - root logger
logging.info("Doing something")
```

### 2. Use Appropriate Log Levels

```python
# Debug - detailed diagnostic
def process_data(data):
    logger.debug(f"Processing {len(data)} items")
    for item in data:
        logger.debug(f"Processing item: {item}")

# Info - general progress
logger.info("Starting batch processing")
logger.info(f"Processed {count} items")

# Warning - unexpected but handled
logger.warning("Using default configuration")
logger.warning(f"Retry attempt {attempt}")

# Error - something failed
logger.error("Failed to connect to database")
logger.error(f"API request failed: {response.status_code}")

# Critical - system failure
logger.critical("Database connection lost")
logger.critical("Out of memory")
```

### 3. Include Context

```python
# Good - contextual information
logger.info(f"User {user_id} logged in from {ip_address}")
logger.error(f"Failed to process order {order_id}: {error}")

# Bad - vague messages
logger.info("User logged in")
logger.error("Something went wrong")
```

### 4. Don't Log Sensitive Data

```python
# Bad - logging sensitive data
logger.info(f"User login: {username}, password: {password}")
logger.debug(f"API key: {api_key}")

# Good - masking sensitive data
logger.info(f"User {username} logged in")
logger.debug(f"Using API key: {api_key[:4]}****")
```

## Troubleshooting

### Common Issues

1. **Colors not showing**
   - Check terminal supports ANSI colors
   - Verify `colorlog` is installed
   - Try `enable_colors: true` in config

2. **Logs not written to file**
   - Check file path exists
   - Verify write permissions
   - Check disk space

3. **Too verbose logging**
   - Increase minimum log level
   - Use module-specific levels
   - Add filters

4. **Missing log messages**
   - Check logger name hierarchy
   - Verify handler configuration
   - Check log level thresholds

## Dependencies

- `colorlog` - Colored console output
- `logging` - Standard library logging

## Related Documentation

- [xcore.md](xcore.md) - Core application logging
- [configurations.md](configurations.md) - Logger configuration
