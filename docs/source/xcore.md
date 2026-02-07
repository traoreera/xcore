# xcore - Core Application Package

## Overview

The `xcore` module is the heart of the framework, managing the application lifecycle, configuration loading, and core integrations including the hook system.

## Module Structure

```
xcore/
├── __init__.py          # FastAPI app instance export
├── appcfg.py            # Configuration loader & logger setup
├── events.py            # Event handling system
├── manage.py            # Application management utilities
├── middleware.py        # Middleware registration
└── view.py              # View utilities
```

## Core Components

### `__init__.py`

Exports the main FastAPI application instance.

**Exports:**
- `app` - The main FastAPI application instance

### `appcfg.py`

Central configuration loader and logger initialization.

**Key Functions:**

#### `load_config()`
Loads and validates the main configuration from `config.json`.

```python
def load_config() -> Xcorecfg:
    """Load and validate configuration from config.json"""
```

#### `setup_logging()`
Initializes the logging system with colorized output.

```python
def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup colored logging for the application"""
```

**Usage:**
```python
from xcore.appcfg import load_config, setup_logging

config = load_config()
logger = setup_logging(config.log_level)
```

### `events.py`

Event handling system for application lifecycle events.

**Features:**
- Startup event handlers
- Shutdown event handlers
- Plugin lifecycle events
- Custom event registration

**Usage:**
```python
from xcore.events import xhooks

@xhooks.on('xcore.startup')
async def init_database():
    """Initialize database on startup"""
    pass

@xhooks.on('xcore.shutdown')
async def cleanup_resources():
    """Cleanup resources on shutdown"""
    pass
```

### `manage.py`

Application management utilities.

**Key Functions:**

#### `init_app()`
Initializes the complete application with all components.

```python
def init_app() -> FastAPI:
    """Initialize the FastAPI application with all components"""
```

#### `get_app_status()`
Returns the current application status.

```python
def get_app_status() -> dict:
    """Get current application status"""
```

### `middleware.py`

Middleware registration and management.

**Key Functions:**

#### `register_middleware()`
Registers middleware with the FastAPI application.

```python
def register_middleware(app: FastAPI, middleware_class: type) -> None:
    """Register a middleware class with the app"""
```

#### `setup_middlewares()`
Configures all default middlewares from configuration.

```python
def setup_middlewares(app: FastAPI) -> None:
    """Setup all configured middlewares"""
```

### `view.py`

View utilities for template rendering and response handling.

**Key Functions:**

#### `render_template()`
Renders a Jinja2 template with context.

```python
def render_template(template_name: str, context: dict = None) -> Response:
    """Render a template with the given context"""
```

## Configuration Integration

The xcore module integrates with the `configurations` module to load settings:

```python
from configurations import Xcorecfg

config: Xcorecfg = load_config()
```

## Hook System Integration

The core module initializes the hook system:

```python
from hooks import HookManager

hook_manager = HookManager()
hook_manager.register("app.startup", init_function)
```

## Usage Example

```python
from xcore import app
from xcore.appcfg import load_config
from xcore.manage import init_app
from xcore.middleware import setup_middlewares

# Initialize application
config = load_config()
app = init_app()

# Setup middlewares
setup_middlewares(app)

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Dependencies

- `fastapi` - Web framework
- `configurations` - Configuration management
- `loggers` - Logging system
- `hooks` - Hook system
- `manager` - Plugin management

## Related Documentation

- [configurations.md](configurations.md) - Configuration system
- [hooks.md](hooks.md) - Hook system
- [manager.md](manager.md) - Plugin management
