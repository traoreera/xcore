---
title: Database Services
description: Guide to using SQLAlchemy (Async/Sync), MongoDB, and Redis adapters in Xcore.
icon: material/database
---

# Database Services

Xcore provides a unified `DatabaseManager` that abstracts different database engines and drivers into easy-to-use adapters. It supports SQLAlchemy (for SQL databases), Motor (for MongoDB), and `redis-py` (for Redis).

---

### Prerequisites

- [x] [Service Container](./services.md) overview understood
- [x] Relevant driver installed (e.g., `aiosqlite`, `asyncpg`, `motor`, `redis`)

---

### Key Concepts

#### The Adapter Pattern
Xcore uses adapters to normalize interactions across different database types. Every adapter provides a `ping()` method for health checks and a specific session/client management pattern.

#### Multi-Connection Support
You can define multiple database connections in your configuration. The first one defined is automatically aliased as `db` for convenience, but all are accessible by their defined names.

```mermaid
graph LR
    K[Xcore Kernel] --> M[Database Manager]
    M --> A1[AsyncSQLAdapter: 'default']
    M --> A2[MongoDBAdapter: 'logs']
    M --> A3[RedisAdapter: 'queue']

    A1 -.->|alias| DB[db]
```

---

### Practical Guide

#### 1. SQL Databases (SQLAlchemy Async)
This is the recommended adapter for most applications. It supports standard SQL engines like PostgreSQL, MySQL, and SQLite.

```python linenums="1" hl_lines="7"
from xcore import TrustedBase
from sqlalchemy import text

class Plugin(TrustedBase):
    async def get_users(self):
        db = self.get_service("db")
        async with db.session() as session:  # (1)!
            result = await session.execute(text("SELECT * FROM users"))
            return result.fetchall()
```

1.  The `session()` context manager automatically handles `commit()` on success and `rollback()` on exception.

#### 2. MongoDB
Supports asynchronous interaction with MongoDB using the Motor driver.

```python linenums="1"
class Plugin(TrustedBase):
    async def log_event(self, event_data):
        mongo = self.get_service("mongodb")
        await mongo.db.events.insert_one(event_data)
```

#### 3. Redis
A dedicated adapter for using Redis as a primary data store (separate from the Cache service).

```python linenums="1"
class Plugin(TrustedBase):
    async def set_state(self, key, value):
        redis = self.get_service("redis")
        await redis.set(key, value)
```

---

### YAML Configuration

Define your connections in the `services.databases` section.

```yaml linenums="1" title="xcore.yaml"
services:
  databases:
    default:  # (1)!
      type: "postgresql+aio"
      url: "postgresql+asyncpg://user:pass@localhost/dbname"
      pool_size: 20
      echo: false

    logs:     # (2)!
      type: "mongodb"
      url: "mongodb://localhost:27017"
      database: "app_logs"

    state:    # (3)!
      type: "redis"
      url: "redis://localhost:6379/1"
```
Autre configuration possible en production
```yaml linenums="1" title="xcore.yaml"
services:
  databases:

    # ── MySQL / MariaDB (prod) ─────────────────────────────
    default:
      type: sqlasync        # ou postgresql+aio
      url: mysql+aiomysql://user:pass@host:3306/db
      pool_size: 10
      max_overflow: 20
      pool_pre_ping: true
      pool_recycle: 1800           # < wait_timeout MySQL (SHOW VARIABLES LIKE 'wait_timeout')
      pool_timeout: 30
      pool_reset_on_return: rollback
      isolation_level: READ COMMITTED
      connect_args:
        connect_timeout: 10        # timeout TCP initial
        read_timeout: 30           # timeout lecture réseau
        write_timeout: 30          # timeout écriture réseau
        charset: utf8mb4

    # ── PostgreSQL (prod) ──────────────────────────────────
    pg:
      type: sqlasync
      url: postgresql+asyncpg://user:pass@host/db
      pool_size: 10
      max_overflow: 20
      pool_pre_ping: true
      pool_recycle: 3600
      pool_reset_on_return: rollback
      isolation_level: READ COMMITTED
      connect_args:
        command_timeout: 30
        timeout: 10                # timeout connexion initiale

    # ── SQLite (dev/test uniquement) ───────────────────────
    dev:
      type: sqlasync
      url: sqlite+aiosqlite:///./dev.db
      echo: true
      # pool_recycle / pool_timeout ignorés pour SQLite

```

1.  **Async SQL**: Use `+aio` or `+asyncpg` suffixes for async drivers.
2.  **MongoDB**: Requires the `database` key to select the target DB.
3.  **Redis**: Directly uses the Redis URL.

---

### Multi-Tenancy (PostgreSQL)

Xcore supports automatic schema isolation for PostgreSQL using the `TenantAwareDB` middleware. When `tenancy.isolate_db` is enabled, the framework will automatically execute `SET search_path TO <tenant_id>` at the start of every session.

!!! info "PostgreSQL Specific"
    Schema isolation via `search_path` is only supported on PostgreSQL. For other databases, you must handle isolation manually (e.g., by prefixing table names).

---

### API Reference

#### Common Adapter Methods
| Method | Return Type | Description |
|--------|-------------|-------------|
| `ping()` | `tuple[bool, str]` | Used by the health checker to verify the connection. |
| `disconnect()` | `None` | Gracefully closes the connection/pool. |

#### `AsyncSQLAdapter`
| Method / Attribute | Type | Description |
|--------------------|------|-------------|
| `session()` | `AsyncGenerator` | Context manager for an `AsyncSession`. |
| `execute(sql, params)` | `Any` | Execute a raw SQL string using the engine directly. |
| `engine` | `AsyncEngine` | Access the underlying SQLAlchemy engine. |

---

### Common Errors & Pitfalls

!!! danger "ImportError: driver not found"
    Xcore does not include all database drivers by default to keep the core lean.
    **Fix**: Install the missing driver (e.g., `pip install asyncpg` or `pip install motor`).

!!! warning "Sync vs. Async Mixup"
    Using a synchronous URL (e.g., `postgresql://`) with the `AsyncSQLAdapter` will result in a runtime error.
    **Fix**: Ensure your URL matches the expected driver (e.g., `postgresql+asyncpg://`).

!!! failure "Session Leak"
    Always use the `async with db.session()` context manager. Manually creating sessions without closing them will quickly exhaust your connection pool.

---

### Best Practices

!!! success "Use Type-Safe Queries"
    While `execute(text(...))` works, we highly recommend using SQLAlchemy's Core or ORM expressions for better security (SQL injection protection) and maintainability.

!!! tip "Pool Sizing"
    Adjust the `pool_size` and `max_overflow` in `xcore.yaml` based on your expected concurrency. For heavy loads, consider using a connection bouncer like PgBouncer.
