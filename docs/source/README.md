# xcore Documentation

Welcome to the xcore framework documentation. xcore is a Multi-Plugins Framework for FastAPI designed to manage dynamic plugins, scheduled tasks, and provide a complete administration interface.

## Table of Contents

### Core Modules

- [xcore](xcore.md) - Core application package
- [configurations](configurations.md) - Configuration management
- [database](database.md) - Database connection & SQLAlchemy
- [hooks](hooks.md) - Hook system for extensibility

### Management & Plugins

- [manager](manager.md) - Plugin & task management framework
- [plugins](plugins.md) - Plugin development guide
- [backgroundtask](backgroundtask.md) - Background task container

### Security & Access Control

- [auth](auth.md) - Authentication & user management
- [admin](admin.md) - Administration & RBAC
- [security](security.md) - Security utilities
- [middleware](middleware.md) - Access control middleware
- [otpprovider](otpprovider.md) - Two-factor authentication

### Infrastructure

- [frontend](frontend.md) - Template engine & MicroUI components
- [cache](cache.md) - Redis-based caching
- [loggers](loggers.md) - Logging configuration
- [tools](tools.md) - Migration & utility scripts

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd xcore

# Install dependencies (using Poetry)
poetry install

# Or using pip
pip install -r requirements.txt
```

### Configuration

Create a `config.json` file:

```json
{
  "app_name": "xcore",
  "debug": false,
  "log_level": "INFO",

  "database": {
    "url": "sqlite:///./app.db"
  },

  "security": {
    "jwt_secret_key": "your-secret-key",
    "access_token_expire_minutes": 30
  },

  "manager": {
    "plugins_directory": "plugins",
    "auto_enable": true
  }
}
```

### Running the Application

```bash
# Run with uvicorn
uvicorn main:app --reload

# Or using the CLI
python -m xcore run
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        FastAPI                          │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │   auth   │  │   admin  │  │ manager  │  │  hooks  │  │
│  │ (routes) │  │ (routes) │  │ (routes) │  │(events) │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘  │
│       │             │             │             │        │
│  ┌────┴─────────────┴─────────────┴─────────────┴────┐  │
│  │              middleware (Access Control)            │  │
│  └─────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌──────────┐  ┌─────────┐  ┌────────┐  │
│  │  plugins   │  │ frontend │  │  cache  │  │ loggers│  │
│  │(dynamic)   │  │(templates│  │ (redis) │  │        │  │
│  └────────────┘  └──────────┘  └─────────┘  └────────┘  │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌─────────────────────────────┐  │
│  │     xcore        │  │       configurations        │  │
│  │ (core lifecycle) │  │         (settings)          │  │
│  └──────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │ database │  │ security │  │  tools   │  │background│  │
│  │(SQLA/etc)│  │(JWT/hash)│  │(migrations│  │  tasks  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Key Features

- **Plugin System**: Dynamic loading with hot reload, sandboxing, and lifecycle management
- **Task Scheduler**: APScheduler with core threading, auto-restart, and retries
- **Authentication**: JWT tokens with role-based and permission-based access
- **Administration**: User/role/permission management API
- **Frontend**: Jinja2 templating with 32+ MicroUI components and DaisyUI themes
- **Database**: SQLAlchemy with Alembic migrations and auto-discovery
- **Caching**: Redis-based with decorator support
- **Security**: Bcrypt hashing, JWT tokens, access control middleware
- **Hooks**: Event-driven extensibility system

## Module Dependencies

```
xcore
├── configurations (base.py, core.py)
├── loggers (logger_config.py)
└── hooks (hooks.py)

manager
├── configurations
├── database
├── loggers
└── hooks

auth
├── database
├── security (hash.py, token.py)
└── loggers

admin
├── auth (User model)
├── database
└── loggers

plugins
├── manager
├── database
├── hooks (optional)
└── frontend (optional)

frontend
├── configurations
└── loggers

cache
├── configurations (redis.py)
└── loggers

middleware
├── auth (token validation)
└── admin (role/permission checking)

tools
├── database
├── configurations (migrations.py)
└── loggers
```

## Development Guide

### Creating a Plugin

See [plugins.md](plugins.md) for detailed instructions.

Quick example:

```python
# plugins/my_plugin/__init__.py
PLUGIN_INFO = {
    "id": "my_plugin",
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "A sample plugin",
    "dependencies": []
}

from .api.routes import router
__all__ = ["router", "PLUGIN_INFO"]
```

```python
# plugins/my_plugin/api/routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/my_plugin", tags=["my_plugin"])

@router.get("/hello")
async def hello():
    return {"message": "Hello from My Plugin!"}
```

### Adding a Background Task

See [backgroundtask.md](backgroundtask.md) for details.

```python
# backgroundtask/taskplugins.py

async def my_scheduled_task():
    """Runs every hour"""
    print("Task executed!")

TASK_DEFINITIONS = [
    {
        "id": "my_task",
        "name": "My Scheduled Task",
        "func": my_scheduled_task,
        "trigger": "interval",
        "trigger_args": {"hours": 1},
        "enabled": True
    }
]
```

### Using Hooks

See [hooks.md](hooks.md) for the hook system.

```python
from hooks import action

@action("user.created")
async def on_user_created(user):
    """Handle new user creation"""
    await send_welcome_email(user.email)
```

### Caching

See [cache.md](cache.md) for caching patterns.

```python
from cache import cached

@cached(ttl=300)
async def get_expensive_data(id: int):
    return await fetch_from_db(id)
```

## API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | Login and get token |
| `/auth/me` | GET | Get current user |
| `/auth/refresh` | POST | Refresh access token |

### Administration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/roles` | GET/POST | List/Create roles |
| `/admin/permissions` | GET/POST | List/Create permissions |
| `/admin/users` | GET | List users |

### Manager

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/manager/plugins` | GET/POST | List/Install plugins |
| `/manager/tasks` | GET/POST | List/Create tasks |

## CLI Commands

```bash
# Plugin management
python -m manager list
python -m manager install /path/to/plugin
python -m manager enable my_plugin
python -m manager disable my_plugin

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Development
uvicorn main:app --reload
```

## Configuration Reference

See [configurations.md](configurations.md) for all options.

Key configuration files:
- `config.json` - Main application configuration
- `alembic.ini` - Database migration configuration
- `.env` - Environment variables (optional)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[License information]

## Support

- Documentation: `/docs` directory
- Issues: [GitHub Issues](https://github.com/...)
- Discussions: [GitHub Discussions](https://github.com/...)

---

**Note**: This documentation is automatically generated. For the most up-to-date information, please refer to the source code and inline documentation.
