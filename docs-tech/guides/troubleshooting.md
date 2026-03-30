# Troubleshooting Guide

Common issues and solutions for XCore.

## Installation Issues

### Poetry Installation Fails

**Problem**: Poetry installation fails or command not found

**Solutions**:

```bash
# Install Poetry
pip install --user poetry

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Or use pipx
pipx install poetry
```

### Dependency Conflicts

**Problem**: Poetry dependency resolution fails

**Solutions**:

```bash
# Clear Poetry cache
poetry cache clear pypi --all

# Update lock file
poetry lock --no-update

# Install with specific Python
poetry env use python3.11
poetry install
```

## Runtime Issues

### Plugin Not Loading

**Problem**: Plugin doesn't appear in loaded plugins

**Check**:

```bash
# Verify plugin structure
ls -la plugins/my_plugin/
# Should show: plugin.yaml, src/main.py

# Check plugin.yaml syntax
cat plugins/my_plugin/plugin.yaml | python -c "import yaml, sys; yaml.safe_load(sys.stdin)"

# Check logs
poetry run xcore plugin list
```

**Solutions**:

1. Check `plugin.yaml` is valid YAML
2. Verify `entry_point` path exists
3. Ensure `name` is unique
4. Check for syntax errors in `main.py`

### Database Connection Errors

**Problem**: Cannot connect to database

**Error Messages**:
```
ConnectionRefusedError: [Errno 111] Connection refused
psycopg2.OperationalError: could not connect to server
```

**Solutions**:

```bash
# Check database is running
pg_isready -h localhost -p 5432

# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Verify environment variables
echo $DATABASE_URL

# Check firewall/network
nc -zv localhost 5432
```

### Redis Connection Errors

**Problem**: Cannot connect to Redis

**Solutions**:

```bash
# Check Redis is running
redis-cli ping

# Test with Python
python -c "import redis; r = redis.from_url('$REDIS_URL'); print(r.ping())"

# Check URL format
# Correct: redis://:password@host:6379/0
```

## Service Issues

### Cache Not Working

**Problem**: Cache returns None or doesn't persist

**Solutions**:

```python
# Check cache configuration
assert xcore.services.has("cache")

cache = xcore.services.get("cache")

# Test basic operations
await cache.set("test", "value", ttl=60)
value = await cache.get("test")
assert value == "value"
```

### Scheduler Not Running Jobs

**Problem**: Scheduled jobs don't execute

**Solutions**:

```yaml
# Verify scheduler is enabled
services:
  scheduler:
    enabled: true
    backend: redis  # or memory
```

```python
# Check scheduler
scheduler = xcore.services.get("scheduler")
jobs = scheduler.get_jobs()
print(f"Scheduled jobs: {len(jobs)}")

# Add test job
def test_job():
    print("Job executed!")

scheduler.add_job(test_job, trigger="interval", seconds=5)
```

## Plugin Development Issues

### Import Errors

**Problem**: Cannot import from xcore.sdk

**Solutions**:

```python
# Correct imports
from xcore.sdk import TrustedBase, ok, error

# If import fails, check:
# 1. Poetry shell is activated
# 2. Package is installed: poetry install
# 3. Python path includes xcore
```

### Service Access Errors

**Problem**: `KeyError: Service 'db' not found`

**Solutions**:

```python
class Plugin(TrustedBase):
    async def on_load(self) -> None:
        # Wait for context to be injected
        if self.ctx is None:
            raise RuntimeError("Context not injected")

        # Check service exists before getting
        if not self.ctx.services.has("db"):
            raise RuntimeError("Database service not available")

        self.db = self.get_service("db")
```

### Async/Await Issues

**Problem**: `RuntimeWarning: coroutine was never awaited`

**Solutions**:

```python
# Correct async/await usage
async def handle(self, action: str, payload: dict) -> dict:
    # Must await async functions
    result = await self.db.fetch("SELECT 1")

    # For sync operations in async context
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, sync_function)

    return ok()
```

## Performance Issues

### High Memory Usage

**Problem**: Application uses too much memory

**Solutions**:

```yaml
# Reduce connection pool sizes
services:
  databases:
    default:
      pool_size: 10
      max_overflow: 5

  cache:
    backend: memory
    max_size: 5000
```

```python
# Clear caches periodically
await self.cache.clear()

# Use streaming for large datasets
async for row in self.db.iter_rows("SELECT * FROM large_table"):
    yield row
```

### Slow Plugin Calls

**Problem**: Plugin actions take too long

**Solutions**:

1. **Use caching**:
```python
async def get_data(self, key):
    return await self.cache.get_or_set(
        key,
        factory=lambda: self._fetch_expensive_data(key),
        ttl=300
    )
```

2. **Database indexing**:
```sql
CREATE INDEX idx_users_email ON users(email);
```

3. **Async operations**:
```python
# Parallel calls
results = await asyncio.gather(
    self.get_service("db").fetch("..."),
    self.get_service("cache").get("..."),
)
```

## Debugging

### Enable Debug Logging

```yaml
# In config
observability:
  logging:
    level: DEBUG
```

```python
# In plugin
import logging

logger = logging.getLogger("my_plugin")

async def handle(self, action: str, payload: dict) -> dict:
    logger.debug(f"Received action: {action}")
    logger.debug(f"Payload: {payload}")

    try:
        result = self._process(payload)
        logger.info(f"Action {action} completed")
        return ok(data=result)
    except Exception as e:
        logger.exception(f"Error in {action}")
        return error(str(e))
```

### Using PDB

```python
async def handle(self, action: str, payload: dict) -> dict:
    import pdb; pdb.set_trace()  # Breakpoint

    # Debug with:
    # (Pdb) p payload
    # (Pdb) p self.ctx.services
    # (Pdb) c  # continue

    return ok()
```

### Health Check Endpoints

```python
def get_router(self):
    from fastapi import APIRouter
    router = APIRouter()

    @router.get("/health")
    async def health():
        checks = {
            "database": await self._check_db(),
            "cache": await self._check_cache(),
            "memory": self._check_memory()
        }

        healthy = all(checks.values())
        return {
            "status": "healthy" if healthy else "unhealthy",
            "checks": checks
        }

    return router
```

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Context not injected` | Accessing ctx before on_load | Wait for on_load to complete |
| `Service 'x' not found` | Service not configured | Check integration.yaml |
| `Plugin not found` | Plugin name incorrect | Check plugin.yaml name |
| `Rate limit exceeded` | Too many calls | Adjust rate_limit config |
| `Signature invalid` | Wrong secret key | Verify PLUGIN_SECRET_KEY |
| `Import error` | Forbidden import in sandbox | Use allowed imports only |

## Getting Help

If you can't resolve your issue:

1. Check [GitHub Issues](https://github.com/traoreera/xcore/issues)
2. Search [Documentation](https://xcore.readthedocs.io)
3. Ask in [Discussions](https://github.com/traoreera/xcore/discussions)
4. Create a minimal reproduction case

### Reporting Bugs

Include:
- XCore version
- Python version
- Operating system
- Full error traceback
- Steps to reproduce
- Minimal code example
