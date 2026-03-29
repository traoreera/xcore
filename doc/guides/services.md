# Working with Services

XCore provides a suite of high-performance services shared across all plugins. This guide explains how to use the built-in services and access them within your plugin.

## 1. Accessing Services

All services are managed by the `ServiceContainer`. In your plugin class (inheriting from `TrustedBase`), you can access them using `self.get_service(name)`.

```python
class MyPlugin(TrustedBase):
    async def on_load(self) -> None:
        # Access built-in services
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.scheduler = self.get_service("scheduler")
```

## 2. Database Service (`db`)

XCore supports multiple SQL and NoSQL databases via an unified adapter interface.

### SQL Databases (PostgreSQL, MySQL, SQLite)
The `db` service typically returns an `AsyncSQLAdapter` (for asynchronous operations) or a `SQLAdapter` (for synchronous operations).

```python
async def get_users(self):
    # Using the asynchronous adapter
    async with self.db.session() as session:
        result = await session.execute("SELECT * FROM users")
        return result.fetchall()
```

### NoSQL Databases (Redis, MongoDB)
XCore also provides specialized adapters for Redis and MongoDB.

```python
async def get_from_mongo(self, user_id: str):
    mongo = self.get_service("mongodb")
    return await mongo.find_one("users", {"id": user_id})
```

## 3. Cache Service (`cache`)

The `cache` service provides a unified interface for both **Memory** (local) and **Redis** backends.

### Basic Operations
-   `get(key: str)`: Retrieve a value from the cache.
-   `set(key: str, value: Any, ttl: int | None = None)`: Store a value with an optional expiration (in seconds).
-   `delete(key: str)`: Remove a value from the cache.
-   `exists(key: str)`: Check if a key exists.

```python
async def cache_example(self):
    # Set a value with a 5-minute TTL
    await self.cache.set("session_123", {"user_id": 45}, ttl=300)

    # Retrieve the value
    session = await self.cache.get("session_123")

    # Check-and-set pattern
    data = await self.cache.get_or_set("heavy_data", self._fetch_heavy_data, ttl=3600)
```

## 4. Scheduler Service (`scheduler`)

XCore includes a powerful scheduler powered by `APScheduler`. It supports interval, date, and cron triggers.

### Scheduling Tasks
-   `add_job(func, trigger, ...)`: Register a new recurring or one-time task.
-   `remove_job(job_id)`: Unregister a task.

```python
async def on_load(self):
    self.scheduler = self.get_service("scheduler")

    # Add an interval job
    self.scheduler.add_job(
        func=self._cleanup,
        trigger="interval",
        minutes=10,
        id="cleanup_job"
    )

def _cleanup(self):
    print("Running periodic cleanup...")
```

## 5. Extensions

Custom shared logic can be implemented as **Extensions**. Extensions are loaded globally and can be accessed by all plugins.

```python
# Access a custom extension
email_service = self.get_service("ext.email_service")
await email_service.send("user@example.com", "Welcome!", "Hello World")
```

## Service Configuration (`xcore.yaml`)

Services are configured in the `services` section of your main configuration file:

```yaml
services:
  cache:
    backend: "redis"  # or "memory"
    url: "redis://localhost:6379/0"
    ttl: 300

  database:
    enabled: true
    databases:
      db:
        url: "postgresql+asyncpg://user:pass@localhost/db"
        pool_size: 20

  scheduler:
    enabled: true
```

## Best Practices

1.  **Use `get_service` in `on_load`**: This ensures services are initialized and available before use.
2.  **Handle Missing Services**: Always check if a service is enabled in the configuration before attempting to use it.
3.  **Use `get_or_set` for Caching**: This simplifies the "fetch from cache, else fetch from source" pattern and prevents race conditions.
4.  **Async/Sync Consistency**: Prefer asynchronous adapters (`AsyncSQLAdapter`) to avoid blocking the main event loop.
