# Configuration Reference

XCore is configured via `integration.yaml` at the project root. Every key can be overridden by an environment variable using the pattern:

```
XCORE__<SECTION>__<KEY>=value
```

`${VAR}` substitution is supported in YAML values.

---

## `app`

```yaml
app:
  name: my-app                  # Application name
  env: development              # development | production
  debug: true
  secret_key: "change-me"       # Used to verify system API calls
  server_key: "change-me"       # Used for inter-service authentication
  server_key_iterations: 100000 # PBKDF2 iterations for server_key
  plugin_prefix: "/app"         # URL prefix for all plugin routes
  plugin_tags: ["api"]          # OpenAPI tags added to plugin routes
  dotenv: "./.env"              # Optional .env file to load

  fastapi:                      # Passed directly to FastAPI()
    title: "My App"
    summary: ""
    description: ""
    version: "1.0.0"
    debug: false
    docs_url: "/docs"
    redoc_url: "/redoc"
    openapi_url: "/openapi.json"
    redirect_slashes: true
    terms_of_service: "https://example.com/terms"
    contact:
      name: "Support"
      email: "support@example.com"
    license_info:
      name: "MIT"

  server:                       # Passed to uvicorn.run()
    app: "main:app"
    host: "0.0.0.0"
    port: 8000
    workers: 1
    reload: false
    log_level: "info"
    proxy_headers: true
    forwarded_allow_ips: "*"
```

!!! danger "Production check"
    XCore refuses to boot in `env: production` if `secret_key`, `server_key`, or `plugins.secret_key`
    are still set to the default value detected at boot time.

---

## `plugins`

```yaml
plugins:
  directory: ./app              # Root directory for plugin discovery
  secret_key: "12345"           # HMAC-SHA256 key for plugin.sig verification
  strict_trusted: false         # true = reject unsigned TrustedBase plugins
  interval: 10                  # Hot-reload watch interval in seconds (0 = disabled)
  entry_point: src/main.py      # Default entry point within each plugin dir

  snapshot:
    extensions: [".log", ".pyc", ".html"]   # File extensions ignored by watcher
    filenames: ["__pycache__", ".env"]      # File names ignored by watcher
    hidden: true                            # Ignore hidden files/dirs
```

---

## `services`

### `databases`

```yaml
services:
  databases:
    db:                               # Key used to access via container.get("db")
      type: sqlasync                  # sqlasync | sql | redis | mongodb
      url: sqlite+aiosqlite:///db.sqlite3
      echo: false
      pool_size: 5
      max_overflow: 10

    analytics:
      type: sqlasync
      url: postgresql+asyncpg://user:pass@host/db

    redis_db:
      type: redis
      url: redis://localhost:6379/0
      max_connections: 50

    mongo:
      type: mongodb
      url: mongodb://localhost:27017/mydb
```

### `cache`

```yaml
services:
  cache:
    backend: redis                    # redis | memory
    url: redis://localhost:6379/0
    ttl: 300                          # default TTL in seconds
    max_size: 10000                   # max entries (memory backend only)
```

### `scheduler`

```yaml
services:
  scheduler:
    enabled: true
    backend: redis                    # redis | memory
    timezone: Europe/Paris

    jobs:                             # static job declarations (optional)
      - id: daily_cleanup
        func: myapp.tasks:cleanup
        trigger: cron
        hour: 2
        minute: 0
      - id: metrics_snapshot
        func: myapp.tasks:snapshot
        trigger: interval
        minutes: 5
```

### `xworker` (Celery)

```yaml
services:
  xworker:
    enabled: true
    name: my-app
    broker_url: redis://localhost:6379/0
    result_backend: redis://localhost:6379/1
    task_default_queue: default
    concurrency: 4
    task_soft_time_limit: 300
    task_time_limit: 360
    task_serializer: json
    result_serializer: json
    accept_content: [json]
    result_expires: 86400

    queues:
      - default
      - emails

    modules:                          # Python modules with @task() definitions
      - app.tasks.emails
```

### `extensions`

```yaml
services:
  extensions:
    email:
      module: extensions.email.service:EmailService
      config:
        smtp_host: smtp.gmail.com
        smtp_port: 587
        smtp_user: ${SMTP_USER}
        smtp_password: ${SMTP_PASSWORD}
        from_address: noreply@example.com
        use_tls: true
```

---

## `observability`

```yaml
observability:
  logging:
    level: DEBUG                      # DEBUG | INFO | WARNING | ERROR | CRITICAL
    format: "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    file: log/app.log
    max_bytes: 52428800               # 50 MB per file
    backup_count: 10                  # 10 rotation files = 500 MB max

  metrics:
    enabled: true
    backend: prometheus               # memory | prometheus | statsd
    prefix: myapp

  tracing:
    enabled: false
    backend: noop                     # noop | opentelemetry | jaeger
    service_name: my-app
    endpoint: null                    # e.g. http://jaeger:4317
```

---

## `security`

```yaml
security:
  allowed_imports:                    # AST import whitelist for sandboxed plugins
    - json
    - math
    - re
    - datetime
    - typing
    - uuid

  forbidden_imports:                  # Explicit deny — overrides allowed_imports
    - os
    - subprocess

  rate_limit_default:
    calls: 200
    period_seconds: 60
```

---

## `tenancy`

```yaml
tenancy:
  enabled: false
  header: "X-Tenant-ID"
  subdomain: false
  default_tenant: "default"
  isolate_cache: true
  isolate_db: true
  isolate_scheduler: false
  enforce_ipc: true
```

---

## `middleware`

```yaml
middleware:
  - name: timing
    module: xcore.kernel.api.middlewares.timing:RequestTimingMiddleware

  - name: my_custom
    module: myapp.mw:MyMiddleware
    config:
      - name: api_key
        type: external          # static value
        value: "${API_KEY}"
      - name: cache_getter
        type: internal          # callable resolved to a service
        value: cache
      - name: event_bus
        type: events            # callable resolved to EventBus
```

---

## `cors`

```yaml
cors:
  allow_origins: ["*", "http://localhost:3000"]
  allow_credentials: false
  allow_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allow_headers: ["*"]
```

---

## Environment Variable Overrides

```bash
XCORE__APP__DEBUG=false
XCORE__APP__ENV=production
XCORE__APP__SECRET_KEY=my-secret
XCORE__PLUGINS__STRICT_TRUSTED=true
XCORE__SERVICES__CACHE__BACKEND=redis
XCORE__SERVICES__CACHE__URL=redis://prod-redis:6379/0
XCORE__TENANCY__ENABLED=true
XCORE__OBSERVABILITY__LOGGING__LEVEL=WARNING
```
