# cache - Caching System Module

## Overview

The `cache` module provides Redis-based caching with decorator support. It offers a high-level API for caching function results, managing cache keys, and setting TTL (Time To Live) values.

## Module Structure

```
cache/
├── __init__.py          # Module exports
└── cached.py            # Cache decorators & CacheManager
```

## Core Components

### CacheManager

Central manager for cache operations.

```python
class CacheManager:
    """
    Redis-based cache manager.

    Features:
    - Key-value storage with TTL
    - Pattern-based key deletion
    - JSON serialization
    - Connection pooling
    """

    def __init__(
        self,
        redis_url: str = None,
        default_ttl: int = 3600,
        key_prefix: str = "cache:"
    ):
        """
        Initialize cache manager.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
            key_prefix: Prefix for all keys
        """

    # Basic operations
    async def get(self, key: str) -> Any:
        """Get value from cache"""

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None
    ) -> bool:
        """Set value in cache with optional TTL"""

    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""

    async def exists(self, key: str) -> bool:
        """Check if key exists"""

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for a key"""

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key"""

    # Pattern operations
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""

    async def keys(self, pattern: str) -> List[str]:
        """Get all keys matching pattern"""

    # Utility operations
    async def clear(self) -> bool:
        """Clear all cache"""

    async def info(self) -> dict:
        """Get Redis server info"""

    async def ping(self) -> bool:
        """Check Redis connection"""
```

### Decorators

#### `@cached`

Decorator for caching function results.

```python
def cached(
    ttl: int = 3600,
    key: str = None,
    key_builder: Callable = None,
    unless: Callable = None
):
    """
    Cache function return value.

    Args:
        ttl: Time to live in seconds
        key: Static cache key (overrides auto-generation)
        key_builder: Function to build cache key from args
        unless: Function to conditionally skip caching

    Usage:
        @cached(ttl=300)
        async def get_user(user_id: int) -> User:
            return await db.get_user(user_id)
    """
```

#### `@cached_property`

Cached property for class methods.

```python
class cached_property:
    """
    Property that caches its result.

    Usage:
        class MyClass:
            @cached_property(ttl=60)
            async def expensive_computation(self):
                return await heavy_calculation()
    """
```

#### `@cache_evict`

Decorator to clear cache entries.

```python
def cache_evict(
    key: str = None,
    pattern: str = None,
    before: bool = False
):
    """
    Evict cache entries when function is called.

    Args:
        key: Specific key to delete
        pattern: Pattern to match keys for deletion
        before: Evict before function call (default: after)

    Usage:
        @cache_evict(pattern="user:*")
        async def update_user(user_id: int, data: dict):
            return await db.update_user(user_id, data)
    """
```

## Usage Examples

### Basic Caching

```python
from cache import cached, CacheManager

# Create manager
cache = CacheManager()

# Cache a function result
@cached(ttl=300)  # Cache for 5 minutes
async def get_user(user_id: int):
    """Fetch user from database (cached)"""
    return await database.fetch_user(user_id)

# Use the function
user1 = await get_user(1)  # Fetches from DB
user2 = await get_user(1)  # Returns from cache
```

### Custom Key Builder

```python
from cache import cached

def build_key(func_name, args, kwargs):
    """Custom key builder"""
    user_id = args[0] if args else kwargs.get('user_id')
    include_extra = kwargs.get('include_extra', False)
    return f"user:{user_id}:extra:{include_extra}"

@cached(ttl=600, key_builder=build_key)
async def get_user_with_relations(user_id: int, include_extra: bool = False):
    return await database.fetch_user(user_id, include_extra)
```

### Conditional Caching

```python
from cache import cached

def skip_cache_for_admin(result):
    """Don't cache if user is admin"""
    return result.is_admin if result else False

@cached(ttl=300, unless=skip_cache_for_admin)
async def get_user(user_id: int):
    return await database.fetch_user(user_id)
```

### Cache Eviction

```python
from cache import cached, cache_evict

@cached(ttl=3600, key_builder=lambda n, a, k: f"user:{a[0]}")
async def get_user(user_id: int):
    return await database.fetch_user(user_id)

@cache_evict(pattern="user:*")  # Clear all user caches
async def update_user(user_id: int, data: dict):
    return await database.update_user(user_id, data)

@cache_evict(key="user:1")  # Clear specific user
async def delete_user(user_id: int):
    return await database.delete_user(user_id)
```

### Direct Cache Operations

```python
from cache import CacheManager

cache = CacheManager()

# Store value
await cache.set("key", {"data": "value"}, ttl=300)

# Retrieve value
value = await cache.get("key")

# Check existence
exists = await cache.exists("key")

# Delete value
await cache.delete("key")

# Pattern deletion
await cache.delete_pattern("user:*")

# Clear all
await cache.clear()
```

### Class Method Caching

```python
from cache import cached

class UserService:
    @cached(ttl=300)
    async def get_user(self, user_id: int):
        return await self.db.fetch_user(user_id)

    @cached(ttl=60)
    async def get_user_count(self):
        return await self.db.count_users()

    @cache_evict(pattern="user:*")
    async def update_user(self, user_id: int, data: dict):
        return await self.db.update_user(user_id, data)
```

### Cached Property

```python
from cache import cached_property

class DataProcessor:
    def __init__(self, data_source):
        self.data_source = data_source

    @cached_property(ttl=300)
    async def processed_data(self):
        """Expensive computation cached for 5 minutes"""
        raw_data = await self.data_source.fetch()
        return self.expensive_processing(raw_data)

    def expensive_processing(self, data):
        # Heavy computation here
        return processed
```

## Configuration

Configuration in `config.json`:

```json
{
  "redis": {
    "enabled": true,
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

### Environment Variables

```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=secret
export REDIS_DEFAULT_TTL=3600
```

## Key Naming Conventions

### Auto-Generated Keys

```python
# Default format: "prefix:module:function:args_hash"
# Example:
# "xcore:services.user:get_user:abc123"
```

### Recommended Patterns

```python
# Entity-based
"user:{user_id}"
"post:{post_id}"
"category:{slug}"

# List-based
"users:page:{page}:size:{size}"
"posts:category:{category_id}"

# Query-based
"search:{query_hash}"
"filter:{filter_params}"
```

## Advanced Features

### Cache Statistics

```python
from cache import CacheManager

cache = CacheManager()

# Get cache info
info = await cache.info()
print(f"Used memory: {info['used_memory_human']}")
print(f"Total keys: {info['db0']['keys']}")

# Check connection
if await cache.ping():
    print("Redis is connected")
```

### Batch Operations

```python
from cache import CacheManager

cache = CacheManager()

# Get multiple values
keys = ["user:1", "user:2", "user:3"]
values = await cache.get_many(keys)

# Set multiple values
items = {
    "user:1": user1_data,
    "user:2": user2_data,
    "user:3": user3_data
}
await cache.set_many(items, ttl=300)
```

### Cache Warming

```python
from cache import CacheManager

cache = CacheManager()

async def warm_cache():
    """Pre-populate cache with common data"""
    users = await database.get_all_users()
    for user in users:
        await cache.set(f"user:{user.id}", user.dict(), ttl=3600)
    print(f"Cached {len(users)} users")
```

### Decorator with Dependency Injection

```python
from fastapi import Depends
from cache import cached

async def get_cache_manager():
    return CacheManager()

@cached(ttl=300)
async def get_user(
    user_id: int,
    cache: CacheManager = Depends(get_cache_manager)
):
    # Custom cache instance
    return await database.fetch_user(user_id)
```

## Best Practices

### 1. Set Appropriate TTL

```python
# Short TTL for frequently changing data
@cached(ttl=60)
async def get_live_data():
    pass

# Long TTL for static data
@cached(ttl=86400)  # 24 hours
async def get_configuration():
    pass

# No TTL for persistent data
@cached(ttl=None)
async def get_reference_data():
    pass
```

### 2. Cache Invalidation Strategy

```python
# Evict related caches on update
@cache_evict(pattern="user:*")
async def update_user(user_id: int, data: dict):
    pass

# Evict specific keys
@cache_evict(keys=["user:list", "user:stats"])
async def create_user(data: dict):
    pass
```

### 3. Handle Cache Failures

```python
from cache import cached

@cached(ttl=300, fallback_on_error=True)
async def get_critical_data():
    """Fallback to function result if cache fails"""
    return await fetch_data()
```

### 4. Avoid Caching Large Objects

```python
# Good - cache IDs only
@cached(ttl=300)
async def get_user_ids():
    return await db.get_user_ids()

# Bad - caching large datasets
@cached(ttl=300)
async def get_all_users():
    return await db.get_all_users()  # Too large!
```

## Testing

### Mock Cache for Testing

```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_cache():
    cache = Mock()
    cache.get = Mock(return_value=None)
    cache.set = Mock(return_value=True)
    return cache

async def test_cached_function(mock_cache):
    with patch('cache.CacheManager', return_value=mock_cache):
        result = await get_user(1)
        mock_cache.get.assert_called_once()
```

### Cache Statistics in Tests

```python
async def test_cache_hit():
    cache = CacheManager()

    # First call - cache miss
    await get_user(1)
    assert cache.get.call_count == 1

    # Second call - cache hit
    await get_user(1)
    assert cache.get.call_count == 2
```

## Troubleshooting

### Common Issues

1. **Connection refused**
   - Check Redis server is running
   - Verify host/port configuration

2. **Serialization errors**
   - Ensure cached objects are JSON serializable
   - Use custom serializer for complex objects

3. **Memory issues**
   - Set appropriate TTL values
   - Use key patterns for bulk deletion
   - Monitor Redis memory usage

4. **Cache stampede**
   - Use cache warming
   - Implement probabilistic early expiration
   - Add request coalescing

## Dependencies

- `redis` - Redis client
- `configurations` - Configuration loading
- `loggers` - Logging

## Related Documentation

- [configurations.md](configurations.md) - Redis configuration
- [manager.md](manager.md) - Plugin cache purging
