# configurations - Configuration Management Module

## Overview

The `configurations` module provides a centralized, typed configuration management system. It supports loading from JSON files, environment variables, and provides validation using Pydantic models.

## Module Structure

```
configurations/
├── __init__.py          # Module exports
├── base.py              # Base configuration classes
├── core.py              # Core configuration (Xcorecfg)
├── deps.py              # Dependencies configuration
├── manager.py           # Manager configuration
├── middleware.py        # Middleware configuration
├── migrations.py        # Migration configuration
├── redis.py             # Redis configuration
└── secure.py            # Security configuration
```

## Core Components

### Base Classes (`base.py`)

#### `BaseConfig`

Base class for all configurations.

```python
class BaseConfig(BaseModel):
    """Base configuration class with common functionality"""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @classmethod
    def from_file(cls, path: str) -> "BaseConfig":
        """Load configuration from JSON file"""

    @classmethod
    def from_env(cls) -> "BaseConfig":
        """Load configuration from environment variables"""

    def to_file(self, path: str) -> None:
        """Save configuration to JSON file"""
```

#### `DatabaseConfig`

```python
class DatabaseConfig(BaseConfig):
    """Database configuration"""

    url: str = Field(default="sqlite:///./app.db")
    echo: bool = Field(default=False)  # SQLAlchemy echo
    pool_size: int = Field(default=5)
    max_overflow: int = Field(default=10)
    pool_timeout: int = Field(default=30)
```

### Core Configuration (`core.py`)

#### `Xcorecfg`

Main application configuration.

```python
class Xcorecfg(BaseConfig):
    """Main xcore configuration"""

    # Application settings
    app_name: str = Field(default="xcore")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Module configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    manager: ManagerConfig = Field(default_factory=ManagerConfig)
    middleware: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    migrations: MigrationsConfig = Field(default_factory=MigrationsConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)

    # Paths
    plugins_dir: str = Field(default="plugins")
    templates_dir: str = Field(default="templates")
    static_dir: str = Field(default="static")
    logs_dir: str = Field(default="logs")

    @validator("log_level")
    def validate_log_level(cls, v):
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()
```

### Security Configuration (`secure.py`)

#### `SecurityConfig`

```python
class SecurityConfig(BaseConfig):
    """Security-related configuration"""

    # JWT settings
    jwt_secret_key: str = Field(default="change-me")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)

    # Password hashing
    password_hash_algorithm: str = Field(default="bcrypt")
    bcrypt_rounds: int = Field(default=12)

    # CORS settings
    cors_origins: List[str] = Field(default=["*"])
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: List[str] = Field(default=["*"])
    cors_allow_headers: List[str] = Field(default=["*"])

    # Rate limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_period: int = Field(default=60)  # seconds
```

### Manager Configuration (`manager.py`)

#### `ManagerConfig`

```python
class ManagerConfig(BaseConfig):
    """Plugin and task manager configuration"""

    # Plugin settings
    plugins_directory: str = Field(default="plugins")
    auto_enable: bool = Field(default=True)
    hot_reload: bool = Field(default=False)
    sandboxing: bool = Field(default=True)
    max_plugins: int = Field(default=100)

    # Task settings
    tasks_directory: str = Field(default="backgroundtask")
    max_tasks: int = Field(default=50)
    task_timeout: int = Field(default=300)  # seconds
    auto_restart_tasks: bool = Field(default=True)
    max_task_retries: int = Field(default=3)

    # Scheduler settings
    scheduler_thread_pool: int = Field(default=10)
    scheduler_job_defaults: dict = Field(default_factory=dict)
```

### Middleware Configuration (`middleware.py`)

#### `MiddlewareConfig`

```python
class AccessRule(BaseModel):
    """Single access control rule"""

    path: str                           # URL path pattern
    methods: List[str] = Field(default=["*"])  # HTTP methods
    roles: List[str] = Field(default=[])       # Required roles
    permissions: List[str] = Field(default=[]) # Required permissions
    public: bool = Field(default=False)        # Public access

class MiddlewareConfig(BaseConfig):
    """Middleware configuration"""

    enabled: bool = Field(default=True)
    access_rules: List[AccessRule] = Field(default_factory=list)
    default_authenticated: bool = Field(default=False)
```

### Migrations Configuration (`migrations.py`)

#### `MigrationsConfig`

```python
class BackupPolicy(BaseModel):
    """Database backup policy"""

    enabled: bool = Field(default=True)
    before_migrate: bool = Field(default=True)
    keep_count: int = Field(default=5)
    location: str = Field(default="backups")

class MigrationsConfig(BaseConfig):
    """Database migration configuration"""

    auto_migrate: bool = Field(default=False)
    auto_discovery: bool = Field(default=True)
    models_package: str = Field(default="models")
    script_location: str = Field(default="alembic")
    backup_policy: BackupPolicy = Field(default_factory=BackupPolicy)
```

### Redis Configuration (`redis.py`)

#### `RedisConfig`

```python
class RedisConfig(BaseConfig):
    """Redis cache configuration"""

    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)

    # Connection pool settings
    max_connections: int = Field(default=50)
    socket_timeout: int = Field(default=5)
    socket_connect_timeout: int = Field(default=5)

    # Default cache settings
    default_ttl: int = Field(default=3600)  # 1 hour
    key_prefix: str = Field(default="xcore:")

    @property
    def connection_url(self) -> str:
        """Build Redis connection URL"""
        if self.password:
            return f"redis://{self.username}:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
```

## Usage Examples

### Loading Configuration

```python
from configurations import Xcorecfg

# Load from file
config = Xcorecfg.from_file("config.json")

# Load from environment (with env var overrides)
config = Xcorecfg.from_env()

# Access nested config
db_url = config.database.url
jwt_secret = config.security.jwt_secret_key
```

### Creating Configuration

```python
from configurations import Xcorecfg, SecurityConfig, DatabaseConfig

config = Xcorecfg(
    app_name="MyApp",
    debug=True,
    log_level="DEBUG",
    database=DatabaseConfig(
        url="postgresql://user:pass@localhost/db",
        echo=True
    ),
    security=SecurityConfig(
        jwt_secret_key="super-secret",
        access_token_expire_minutes=60
    )
)

# Save to file
config.to_file("config.json")
```

### Using with FastAPI

```python
from fastapi import FastAPI, Depends
from configurations import Xcorecfg

app = FastAPI()
config = Xcorecfg.from_file("config.json")

def get_config() -> Xcorecfg:
    return config

@app.get("/config")
async def get_app_config(cfg: Xcorecfg = Depends(get_config)):
    return {
        "app_name": cfg.app_name,
        "debug": cfg.debug
    }
```

### Environment Variable Overrides

```bash
# Override specific values via environment
export XCORE_DEBUG=true
export XCORE_LOG_LEVEL=DEBUG
export XCORE_DATABASE__URL=postgresql://user:pass@localhost/db
export XCORE_SECURITY__JWT_SECRET_KEY=my-secret
export XCORE_REDIS__ENABLED=true
```

### Custom Configuration Section

```python
from configurations.base import BaseConfig

class CustomConfig(BaseConfig):
    """Custom application configuration"""

    api_key: str
    endpoint_url: str
    timeout: int = 30

# Use in main config
class Xcorecfg(BaseConfig):
    custom: CustomConfig = Field(default_factory=CustomConfig)
```

## Configuration File Format

### JSON Configuration (`config.json`)

```json
{
  "app_name": "xcore",
  "debug": false,
  "log_level": "INFO",

  "database": {
    "url": "sqlite:///./app.db",
    "echo": false,
    "pool_size": 5,
    "max_overflow": 10
  },

  "security": {
    "jwt_secret_key": "your-secret-key-change-in-production",
    "jwt_algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "refresh_token_expire_days": 7,
    "password_hash_algorithm": "bcrypt",
    "bcrypt_rounds": 12,
    "cors_origins": ["http://localhost:3000"],
    "cors_allow_credentials": true,
    "rate_limit_requests": 100,
    "rate_limit_period": 60
  },

  "manager": {
    "plugins_directory": "plugins",
    "auto_enable": true,
    "hot_reload": false,
    "sandboxing": true,
    "tasks_directory": "backgroundtask",
    "max_tasks": 50,
    "task_timeout": 300,
    "auto_restart_tasks": true,
    "max_task_retries": 3
  },

  "middleware": {
    "enabled": true,
    "access_rules": [
      {
        "path": "/auth/*",
        "methods": ["POST"],
        "public": true
      },
      {
        "path": "/admin/*",
        "roles": ["admin"],
        "permissions": []
      },
      {
        "path": "/api/*",
        "roles": ["admin", "user"],
        "permissions": []
      }
    ],
    "default_authenticated": false
  },

  "migrations": {
    "auto_migrate": false,
    "auto_discovery": true,
    "models_package": "models",
    "script_location": "alembic",
    "backup_policy": {
      "enabled": true,
      "before_migrate": true,
      "keep_count": 5,
      "location": "backups"
    }
  },

  "redis": {
    "enabled": false,
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": null,
    "max_connections": 50,
    "default_ttl": 3600,
    "key_prefix": "xcore:"
  }
}
```

## Validation

All configurations use Pydantic for validation:

```python
from pydantic import ValidationError
from configurations import Xcorecfg

try:
    config = Xcorecfg.from_file("config.json")
except ValidationError as e:
    print("Configuration error:", e)
```

## Dependencies

- `pydantic` - Data validation and settings
- `python-dotenv` - Environment variable loading

## Related Documentation

- [xcore.md](xcore.md) - Core application (uses configuration)
- [database.md](database.md) - Database configuration
- [cache.md](cache.md) - Redis cache configuration
