# Working with Services

XCore provides a powerful service container that gives plugins access to databases, cache, task scheduling, and custom extensions.

## Service Container Overview

Services are initialized in order:

1. **Databases** — SQL and NoSQL connections
2. **Cache** — Redis or in-memory caching
3. **Scheduler** — Background task scheduling
4. **Extensions** — Custom third-party services

Access services via `self.get_service()` or `self.ctx.services`.

## Database Service

### Configuration

```yaml
# integration.yaml
services:
  databases:
    default:                      # Connection name
      type: postgresql
      url: "${DATABASE_URL}"
      pool_size: 20
      max_overflow: 10
      echo: false                # SQL logging

    async_default:
      type: sqlasync
      url: "${DATABASE_ASYNC_URL}"

    redis_db:
      type: redis
      url: "${REDIS_URL}"
```

### Using Synchronous Database

```python
from xcore.sdk import TrustedBase, ok, error


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.db = self.get_service("db")  # First connection
        # Or by name: self.get_service("default")

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/users")
        def list_users():
            """List users using sync database."""
            with self.db.session() as session:
                result = session.execute(
                    "SELECT id, username, email FROM users"
                )
                users = [
                    {"id": row[0], "username": row[1], "email": row[2]}
                    for row in result.fetchall()
                ]
                return {"users": users}

        @router.post("/users")
        def create_user(data: dict):
            """Create a new user."""
            with self.db.session() as session:
                result = session.execute(
                    """
                    INSERT INTO users (username, email, created_at)
                    VALUES (:username, :email, NOW())
                    RETURNING id
                    """,
                    {
                        "username": data["username"],
                        "email": data["email"]
                    }
                )
                session.commit()
                user_id = result.scalar()
                return {"id": user_id, "status": "created"}

        return router

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "get_user":
            user_id = payload.get("user_id")
            with self.db.session() as session:
                result = session.execute(
                    "SELECT * FROM users WHERE id = :id",
                    {"id": user_id}
                )
                user = result.fetchone()
                if user:
                    return ok(user=dict(user))
                return error("User not found", code="not_found")

        return ok()
```

### Using Asynchronous Database

```python
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.db = self.get_service("async_default")

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/users")
        async def list_users():
            """List users using async database."""
            async with self.db.connection() as conn:
                rows = await conn.fetch(
                    "SELECT id, username, email FROM users"
                )
                return {
                    "users": [dict(row) for row in rows]
                }

        @router.get("/users/{user_id}")
        async def get_user(user_id: int):
            """Get user by ID."""
            async with self.db.connection() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1",
                    user_id
                )
                if row:
                    return dict(row)
                raise HTTPException(404, "User not found")

        @router.post("/users")
        async def create_user(data: dict):
            """Create a new user."""
            async with self.db.connection() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (username, email, created_at)
                    VALUES ($1, $2, NOW())
                    RETURNING id
                    """,
                    data["username"],
                    data["email"]
                )
                return {"id": row["id"], "status": "created"}

        return router
```

### Using Redis as Database

```python
from xcore.sdk import TrustedBase
import json


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.redis = self.get_service("redis_db")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "set_json":
            key = payload["key"]
            value = json.dumps(payload["value"])
            ttl = payload.get("ttl", 3600)

            self.redis.set(key, value, ex=ttl)
            return ok(message="Data stored")

        if action == "get_json":
            key = payload["key"]
            data = self.redis.get(key)
            if data:
                return ok(value=json.loads(data))
            return error("Key not found", code="not_found")

        if action == "delete":
            key = payload["key"]
            self.redis.delete(key)
            return ok(message="Key deleted")

        if action == "list_keys":
            pattern = payload.get("pattern", "*")
            keys = self.redis.keys(pattern)
            return ok(keys=[k.decode() for k in keys])

        return ok()
```

## Cache Service

### Configuration

```yaml
services:
  cache:
    backend: redis      # or "memory"
    url: "${REDIS_URL}"
    ttl: 300           # Default TTL in seconds
    max_size: 10000   # For memory backend only
```

### Basic Usage

```python
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/data")
        async def get_data():
            """Get data with caching."""
            # Try cache first
            cached = await self.cache.get("my_data")
            if cached:
                return {"data": cached, "cached": True}

            # Fetch from database
            data = await self._fetch_expensive_data()

            # Store in cache
            await self.cache.set("my_data", data, ttl=300)

            return {"data": data, "cached": False}

        @router.post("/cache/clear")
        async def clear_cache():
            """Clear the cache."""
            await self.cache.clear()
            return {"message": "Cache cleared"}

        return router

    async def _fetch_expensive_data(self):
        # Simulate expensive operation
        import asyncio
        await asyncio.sleep(1)
        return {"value": "expensive_data"}
```

### Pattern: Get or Set

```python
async def get_user_with_cache(self, user_id: str):
    """Get user with automatic caching."""
    cache_key = f"user:{user_id}"

    # Get or compute and cache
    user = await self.cache.get_or_set(
        cache_key,
        factory=lambda: self._fetch_user_from_db(user_id),
        ttl=600  # 10 minutes
    )

    return user

async def _fetch_user_from_db(self, user_id: str):
    """Fetch user from database."""
    with self.db.session() as session:
        result = session.execute(
            "SELECT * FROM users WHERE id = :id",
            {"id": user_id}
        )
        row = result.fetchone()
        return dict(row) if row else None
```

### Cache Tags and Invalidation

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")

    async def create_user(self, user_data: dict) -> dict:
        """Create user and invalidate user list cache."""
        # Create user in database
        user_id = await self._save_user(user_data)

        # Invalidate list cache
        await self.cache.delete("users:list")
        await self.cache.delete_pattern("users:page:*")

        return {"id": user_id}

    async def update_user(self, user_id: str, data: dict) -> dict:
        """Update user and invalidate cache."""
        # Update in database
        await self._update_user_db(user_id, data)

        # Invalidate specific user cache
        await self.cache.delete(f"user:{user_id}")
        await self.cache.delete("users:list")

        return {"updated": True}
```

## Scheduler Service

### Configuration

```yaml
services:
  scheduler:
    enabled: true
    backend: redis      # or "memory"
    timezone: Europe/Paris
```

### Adding Jobs

```python
from xcore.sdk import TrustedBase
from datetime import datetime, timedelta


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.scheduler = self.get_service("scheduler")

        # Add recurring job
        self.scheduler.add_job(
            func=self._cleanup_task,
            trigger="interval",
            minutes=5,
            id="cleanup_job",
            replace_existing=True
        )

        # Add daily job
        self.scheduler.add_job(
            func=self._daily_report,
            trigger="cron",
            hour=2,
            minute=0,
            id="daily_report"
        )

    def _cleanup_task(self):
        """Run every 5 minutes."""
        print(f"Running cleanup at {datetime.now()}")
        # Cleanup logic here

    def _daily_report(self):
        """Run every day at 2:00 AM."""
        print(f"Generating daily report at {datetime.now()}")
        # Report generation logic

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.post("/schedule")
        async def schedule_task(data: dict):
            """Schedule a one-time task."""
            run_at = data.get("run_at")  # ISO format

            self.scheduler.add_job(
                func=self._scheduled_task,
                trigger="date",
                run_date=run_at,
                args=[data.get("payload")],
                id=f"task_{datetime.now().timestamp()}",
                replace_existing=False
            )

            return {"scheduled": True}

        @router.get("/jobs")
        async def list_jobs():
            """List scheduled jobs for this plugin."""
            jobs = self.scheduler.get_jobs()
            return {
                "jobs": [
                    {
                        "id": job.id,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                        "trigger": str(job.trigger)
                    }
                    for job in jobs
                ]
            }

        return router

    def _scheduled_task(self, payload: dict):
        """Execute scheduled task."""
        print(f"Executing scheduled task with: {payload}")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "schedule":
            # Schedule for 1 minute from now
            run_at = datetime.now() + timedelta(minutes=1)

            self.scheduler.add_job(
                func=self._ipc_scheduled_task,
                trigger="date",
                run_date=run_at,
                args=[payload],
                id=f"ipc_task_{datetime.now().timestamp()}"
            )

            return ok(scheduled_for=run_at.isoformat())

        return ok()

    def _ipc_scheduled_task(self, payload: dict):
        """Handle scheduled IPC task."""
        print(f"IPC scheduled task executed: {payload}")
```

### Scheduler Patterns

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.scheduler = self.get_service("scheduler")
        self.jobs = []

        # Schedule cleanup job
        job = self.scheduler.add_job(
            func=self._cleanup_expired_sessions,
            trigger="interval",
            minutes=30,
            id=f"{self.__class__.__name__}_cleanup"
        )
        self.jobs.append(job.id)

    async def on_unload(self) -> None:
        """Remove plugin jobs on unload."""
        for job_id in self.jobs:
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass

    def _cleanup_expired_sessions(self):
        """Cleanup job that runs every 30 minutes."""
        try:
            # Get database service
            db = self.get_service("db")
            with db.session() as session:
                session.execute(
                    "DELETE FROM sessions WHERE expires_at < NOW()"
                )
                session.commit()
        except Exception as e:
            print(f"Cleanup error: {e}")
```

## Custom Extensions

Configure custom services in your configuration:

```yaml
services:
  extensions:
    email:
      type: smtp
      host: "${SMTP_HOST}"
      port: "${SMTP_PORT}"
      user: "${SMTP_USER}"
      password: "${SMTP_PASSWORD}"
      tls: true

    storage:
      type: s3
      bucket: "${S3_BUCKET}"
      region: "${AWS_REGION}"
```

Access extensions:

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.email = self.get_service("ext.email")
        self.storage = self.get_service("ext.storage")

    async def send_notification(self, user_email: str, message: str):
        """Send email notification."""
        await self.email.send(
            to=user_email,
            subject="Notification",
            body=message
        )

    async def upload_file(self, file_data: bytes, filename: str):
        """Upload file to storage."""
        url = await self.storage.upload(
            data=file_data,
            path=f"uploads/{filename}"
        )
        return url
```

## Service Health Checks

```python
class Plugin(TrustedBase):

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/health")
        async def health_check():
            """Check service health."""
            results = {}

            # Check database
            try:
                db = self.get_service("db")
                with db.session() as session:
                    session.execute("SELECT 1")
                results["database"] = {"status": "ok"}
            except Exception as e:
                results["database"] = {"status": "error", "error": str(e)}

            # Check cache
            try:
                cache = self.get_service("cache")
                await cache.set("health_check", "ok", ttl=1)
                results["cache"] = {"status": "ok"}
            except Exception as e:
                results["cache"] = {"status": "error", "error": str(e)}

            # Overall status
            all_ok = all(r["status"] == "ok" for r in results.values())
            return {
                "status": "healthy" if all_ok else "unhealthy",
                "services": results
            }

        return router
```

## Best Practices

1. **Get services in `on_load()`**: Initialize service references during load
2. **Handle service unavailability**: Wrap service calls in try/except
3. **Close connections**: Clean up in `on_unload()`
4. **Use connection pooling**: Let XCore manage connections
5. **Cache expensive operations**: Use the cache service wisely

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        """Initialize all service references."""
        try:
            self.db = self.get_service("db")
            self.cache = self.get_service("cache")
            self.scheduler = self.get_service("scheduler")
            self.initialized = True
        except KeyError as e:
            print(f"Missing required service: {e}")
            self.initialized = False

    async def handle(self, action: str, payload: dict) -> dict:
        """Handle actions with proper error handling."""
        if not getattr(self, "initialized", False):
            return error("Plugin not properly initialized")

        try:
            # Your logic here
            return ok()
        except Exception as e:
            return error(str(e), code="internal_error")
```

## Next Steps

- [Event System](events.md)
- [Security Best Practices](security.md)
- [Testing Plugins](testing.md)
