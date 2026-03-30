# Working with Services

The `ServiceContainer` provides access to global infrastructure shared across all plugins.

---

## 1. Database Service (`db`)

The `db` service supports multiple engines and provides typed adapters for SQL and NoSQL.

### A. SQL Patterns (PostgreSQL/SQLite)
We recommend using the `AsyncSQLAdapter` for non-blocking database operations.

```python
async def get_user_tasks(self, user_id: int):
    db = self.get_service("db")
    async with db.session() as session:
        result = await session.execute(
            "SELECT * FROM tasks WHERE user_id = :uid",
            {"uid": user_id}
        )
        return [dict(row) for row in result.fetchall()]
```

### B. Redis Patterns
The Redis service is ideal for distributed locks, counters, and high-frequency data.

```python
async def rate_limit_check(self, user_id: str):
    redis = self.get_service("redis")
    key = f"limit:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    return count <= 100
```

---

## 2. Cache Service (`cache`)

Unified interface for `memory` and `redis` backends.

### `get_or_set` Pattern
Simplifies the "check cache, then fetch" logic.

```python
data = await self.cache.get_or_set(
    f"profile:{id}",
    factory=lambda: self._fetch_profile_from_db(id),
    ttl=3600
)
```

---

## 3. Scheduler Service (`scheduler`)

Powered by APScheduler, allowing both one-time and recurring tasks.

```python
def sync_data(self):
    print("Syncing data...")

async def on_load(self):
    scheduler = self.get_service("scheduler")
    # Add a CRON job
    scheduler.add_job(
        self.sync_data,
        trigger="cron",
        hour="0",
        minute="0",
        id="daily_sync"
    )
```

---

## 4. Custom Extensions

Extensions are global services loaded from the `extensions/` directory.

```python
# In extensions/my_ext/extension.py
class MyExtension:
    def __init__(self, config):
        self.config = config
    def ping(self):
        return "pong"

# In your Plugin
async def on_load(self):
    ext = self.get_service("ext.my_ext")
    print(ext.ping())
```
