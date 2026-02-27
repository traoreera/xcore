# Configuration Reference

Complete reference for XCore configuration options.

## Configuration File

XCore uses YAML configuration with environment variable substitution.

```yaml
# integration.yaml
app:
  name: my-app
  env: production
  secret_key: ${APP_SECRET_KEY}

plugins:
  directory: ./plugins
  secret_key: ${PLUGIN_SECRET_KEY}

services:
  databases:
    default:
      type: postgresql
      url: "${DATABASE_URL}"
```

## Sections

### app

Application-level configuration.

```yaml
app:
  name: my-app                    # Application name
  env: production                 # Environment: development | staging | production
  debug: false                   # Debug mode (enables detailed errors)
  secret_key: ${APP_SECRET_KEY}  # Secret key for signing (min 32 chars)
  dotenv: "./.env"               # Path to .env file
  plugin_prefix: "/plugin"       # URL prefix for plugin endpoints
  plugin_tags:                   # Tags for plugin routes
    - "my-app"
    - "v2"
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | required | Application identifier |
| `env` | string | `production` | Environment name |
| `debug` | boolean | `false` | Enable debug mode |
| `secret_key` | string | required | Application secret key |
| `dotenv` | string | `null` | Path to .env file |
| `plugin_prefix` | string | `/plugin` | URL prefix for plugin routes |
| `plugin_tags` | list | `[]` | FastAPI tags for plugin routes |

### plugins

Plugin management configuration.

```yaml
plugins:
  directory: ./plugins             # Plugin directory path
  secret_key: ${PLUGIN_SECRET_KEY} # HMAC key for plugin signing
  strict_trusted: false           # Require signatures for trusted plugins
  interval: 0                     # Hot reload interval (0 = disabled)
  entry_point: src/main.py       # Default entry point

  snapshot:                       # File watching configuration
    extensions:                   # Excluded file extensions
      - ".log"
      - ".pyc"
      - ".tmp"
    filenames:                  # Excluded file names
      - "__pycache__"
      - ".env"
      - ".DS_Store"
    hidden: true                 # Exclude hidden files
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `directory` | string | `./plugins` | Plugin directory path |
| `secret_key` | string | `null` | Signing key for trusted plugins |
| `strict_trusted` | boolean | `false` | Require signatures |
| `interval` | integer | `0` | Watch interval in seconds |
| `entry_point` | string | `src/main.py` | Default entry point |

### services.databases

Database connections configuration.

```yaml
services:
  databases:
    # PostgreSQL connection
    default:
      type: postgresql
      url: "${DATABASE_URL}"
      pool_size: 20
      max_overflow: 10
      echo: false

    # Async PostgreSQL
    async_default:
      type: sqlasync
      url: "${DATABASE_ASYNC_URL}"
      echo: false

    # MySQL
    mysql_db:
      type: mysql
      url: "mysql+pymysql://user:pass@host/db"
      pool_size: 10

    # SQLite
    sqlite_db:
      type: sqlite
      url: "sqlite:///./app.db"

    # Redis as database
    redis_db:
      type: redis
      url: "${REDIS_URL}"
      max_connections: 50
```

#### PostgreSQL Options

```yaml
type: postgresql
url: "postgresql+psycopg2://user:pass@host:5432/db"
pool_size: 20              # Connection pool size
max_overflow: 10           # Overflow connections
echo: false               # SQL logging
pool_pre_ping: true       # Validate connections
pool_recycle: 3600        # Recycle connections after seconds
connect_timeout: 30       # Connection timeout
```

#### Async PostgreSQL Options

```yaml
type: sqlasync
url: "postgresql+asyncpg://user:pass@host:5432/db"
echo: false
pool_size: 20
max_overflow: 10
pool_pre_ping: true
```

#### MySQL Options

```yaml
type: mysql
url: "mysql+pymysql://user:pass@host:3306/db"
pool_size: 10
max_overflow: 5
echo: false
```

#### SQLite Options

```yaml
type: sqlite
url: "sqlite:///./app.db"           # File-based
# or
url: "sqlite:///:memory:"           # In-memory

# Additional options
check_same_thread: false            # Allow threads (default: false)
```

#### Redis Options

```yaml
type: redis
url: "redis://localhost:6379/0"
# or with password
url: "redis://:password@localhost:6379/0"

max_connections: 50                 # Connection pool size
decode_responses: true             # Decode responses to str
socket_connect_timeout: 5           # Connection timeout
socket_timeout: 5                   # Socket timeout
```

### services.cache

Cache service configuration.

```yaml
services:
  cache:
    backend: redis          # redis | memory
    url: "${REDIS_URL}"    # Required for redis backend
    ttl: 300               # Default TTL in seconds
    max_size: 10000       # For memory backend only
    prefix: "cache:"      # Key prefix
```

#### Redis Backend

```yaml
backend: redis
url: "redis://localhost:6379/0"
ttl: 300
prefix: "xcore:"
```

#### Memory Backend

```yaml
backend: memory
ttl: 300
max_size: 10000          # Max items in cache
```

### services.scheduler

Task scheduler configuration using APScheduler.

```yaml
services:
  scheduler:
    enabled: true
    backend: redis          # redis | memory | sqlalchemy
    url: "${REDIS_URL}"    # Required for redis backend
    timezone: Europe/Paris

    # Predefined jobs (optional)
    jobs:
      - id: cleanup_sessions
        func: myapp.tasks:cleanup_sessions
        trigger: cron
        hour: 2
        minute: 0

      - id: metrics_snapshot
        func: myapp.tasks:snapshot_metrics
        trigger: interval
        minutes: 5
```

#### Job Configuration

```yaml
jobs:
  - id: unique_job_id
    func: module.path:function_name
    trigger: cron | interval | date

    # Cron trigger
    trigger: cron
    year: "*"
    month: "*"
    day: "*"
    week: "*"
    day_of_week: "*"
    hour: "*"
    minute: "*"
    second: "0"

    # Interval trigger
    trigger: interval
    weeks: 0
    days: 0
    hours: 0
    minutes: 5
    seconds: 0

    # Date trigger (one-time)
    trigger: date
    run_date: "2024-12-25 00:00:00"

    # Common options
    args: []              # Positional arguments
    kwargs: {}           # Keyword arguments
    coalesce: true       # Coalesce missed executions
    max_instances: 1      # Max concurrent instances
    misfire_grace_time: 3600  # Seconds to allow misfires
```

### services.extensions

Custom service extensions.

```yaml
services:
  extensions:
    email:
      type: smtp
      host: "${SMTP_HOST}"
      port: 587
      user: "${SMTP_USER}"
      password: "${SMTP_PASSWORD}"
      tls: true
      from_address: noreply@example.com

    storage:
      type: s3
      bucket: "${S3_BUCKET}"
      region: "${AWS_REGION}"
      access_key: "${AWS_ACCESS_KEY}"
      secret_key: "${AWS_SECRET_KEY}"

    custom_service:
      type: custom
      module: myapp.services.custom
      config:
        key: value
```

### observability

Logging, metrics, and tracing configuration.

```yaml
observability:
  logging:
    level: INFO                     # DEBUG | INFO | WARNING | ERROR | CRITICAL
    format: "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    file: /var/log/xcore/app.log
    max_bytes: 52428800            # 50 MB
    backup_count: 10               # Keep 10 files

  metrics:
    enabled: true
    backend: prometheus              # memory | prometheus | statsd
    prefix: xcore                  # Metric prefix
    port: 9090                     # Prometheus port (if applicable)

  tracing:
    enabled: false
    backend: noop                  # noop | opentelemetry | jaeger
    service_name: my-app
    endpoint: http://jaeger:4317   # OTLP endpoint
    sampling_rate: 1.0
```

#### Logging Options

```yaml
logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  file: /var/log/xcore/app.log
  max_bytes: 52428800
  backup_count: 10

  # Console output
  console: true
  console_level: DEBUG

  # Structured logging (JSON)
  json: false
```

#### Metrics Backends

**Prometheus**:
```yaml
metrics:
  enabled: true
  backend: prometheus
  prefix: xcore
  # Exposed at /metrics
```

**StatsD**:
```yaml
metrics:
  enabled: true
  backend: statsd
  host: localhost
  port: 8125
  prefix: xcore
```

**Memory** (development only):
```yaml
metrics:
  enabled: true
  backend: memory
```

### security

Security configuration for sandboxed plugins.

```yaml
security:
  # Allowed imports for sandboxed plugins
  allowed_imports:
    - json
    - re
    - math
    - datetime
    - time
    - random
    - typing
    - collections
    - itertools
    - functools
    - hashlib
    - base64
    - uuid
    - decimal
    - copy
    - string
    - dataclasses
    - enum
    - asyncio
    - logging

  # Forbidden imports (overrides allowed)
  forbidden_imports:
    - os
    - sys
    - subprocess
    - shutil
    - signal
    - ctypes
    - socket
    - ssl
    - http
    - urllib
    - httpx
    - requests
    - aiohttp
    - importlib
    - builtins
    - exec
    - eval
    - compile
    - pickle

  # Default rate limiting
  rate_limit_default:
    calls: 200
    period_seconds: 60
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_SECRET_KEY` | Application secret | `openssl rand -hex 32` |
| `PLUGIN_SECRET_KEY` | Plugin signing key | `openssl rand -hex 32` |
| `DATABASE_URL` | Database connection | `postgresql://user:pass@host/db` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_ASYNC_URL` | Async database URL | Same as DATABASE_URL |
| `REDIS_URL` | Redis connection | None |
| `SENTRY_DSN` | Sentry error tracking | None |
| `XCORE_CONFIG` | Config file path | `integration.yaml` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Complete Example

```yaml
# ═════════════════════════════════════════════════════════════════
# XCore Production Configuration
# ═════════════════════════════════════════════════════════════════

app:
  name: my-production-app
  env: production
  debug: false
  secret_key: ${APP_SECRET_KEY}
  dotenv: ".env"
  plugin_prefix: "/v1/plugins"
  plugin_tags:
    - "api"
    - "v1"

plugins:
  directory: ./plugins
  secret_key: ${PLUGIN_SECRET_KEY}
  strict_trusted: true
  interval: 0
  entry_point: src/main.py
  snapshot:
    extensions: [".log", ".pyc", ".tmp"]
    filenames: ["__pycache__", ".env"]
    hidden: true

services:
  databases:
    default:
      type: postgresql
      url: ${DATABASE_URL}
      pool_size: 20
      max_overflow: 10
      echo: false
      pool_pre_ping: true
      pool_recycle: 3600

    async_default:
      type: sqlasync
      url: ${DATABASE_ASYNC_URL}
      pool_size: 20
      echo: false

    redis_db:
      type: redis
      url: ${REDIS_URL}
      max_connections: 50
      decode_responses: true

  cache:
    backend: redis
    url: ${REDIS_URL}
    ttl: 300
    prefix: "cache:"

  scheduler:
    enabled: true
    backend: redis
    url: ${REDIS_URL}
    timezone: UTC

  extensions:
    email:
      type: smtp
      host: ${SMTP_HOST}
      port: ${SMTP_PORT}
      user: ${SMTP_USER}
      password: ${SMTP_PASSWORD}
      tls: true
      from_address: ${SMTP_FROM}

observability:
  logging:
    level: WARNING
    format: "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    file: /var/log/xcore/app.log
    max_bytes: 52428800
    backup_count: 10

  metrics:
    enabled: true
    backend: prometheus
    prefix: xcore

  tracing:
    enabled: false
    backend: noop

security:
  allowed_imports:
    - json
    - re
    - math
    - datetime
    - typing
    - asyncio
    - logging

  forbidden_imports:
    - os
    - sys
    - subprocess
    - exec
    - eval

  rate_limit_default:
    calls: 200
    period_seconds: 60
```

## Configuration Loading

### Loading Order

1. Default values
2. Configuration file
3. Environment variables (for substitutions)
4. Runtime overrides

### Runtime Configuration

```python
from xcore import Xcore

# Load specific config file
app = Xcore(config_path="production.yaml")

# Or use default (integration.yaml)
app = Xcore()

# Override at runtime
app._config.app.debug = True
```

## Validation

Validate your configuration:

```bash
# Using CLI
xcore validate --config integration.yaml

# Or Python
from xcore.configurations.loader import ConfigLoader
try:
    config = ConfigLoader.load("integration.yaml")
    print("✅ Configuration valid")
except Exception as e:
    print(f"❌ Configuration error: {e}")
```
