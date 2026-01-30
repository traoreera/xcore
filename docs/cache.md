# Module Documentation: cache/

The `cache/` module provides a robust caching mechanism leveraging Redis to improve application performance by storing and retrieving frequently accessed data. It offers a `CacheManager` for direct cache operations and a `Cached` decorator for easily caching function results.

## Files and Their Roles

*   **`cache/__init__.py`**: (Likely empty or for package initialization).
*   **`cache/cached.py`**: Contains the implementation of the `CacheManager` class and the `Cached` decorator class, which together provide the caching functionality.

## Key Concepts and Functionality

### Redis Integration

The caching system is built upon **Redis**, an in-memory data store. The connection details for Redis (host, port, default TTL) are loaded dynamically from the `config.json` file via `configurations.redis.Rediscfg`.

### `CacheManager` Class

The `CacheManager` class provides the low-level interface for interacting with the Redis cache:

*   **Initialization**: Connects to the Redis server using parameters from `config.json`.
*   **`get(key: str)`**: Retrieves a value from the cache associated with the given `key`. It automatically handles JSON deserialization.
*   **`set(key: str, value: Any)`**: Stores a `value` in the cache under the given `key`. It handles JSON serialization, with special considerations for Pydantic `BaseModel` instances, converting them to dictionaries before serialization.
*   **`remove(key: str)`**: Deletes a specific key-value pair from the cache.
*   **`flush_namespace(namespace: str | None = None)`**: Removes all keys within a specified namespace (or the default namespace if none is provided). This is useful for invalidating groups of related cache entries.

### `Cached` Decorator Class

The `Cached` class provides a higher-level, decorator-based approach to caching function results, making it easy to integrate caching into your application logic:

*   **`@cached(func)`**:
    *   This decorator wraps a function and automatically caches its return value.
    *   When the decorated function is called, the decorator first attempts to retrieve the result from the cache using a key derived from the function's module, name, and arguments.
    *   If a cached value exists, it's returned immediately, avoiding redundant computation.
    *   If no cached value is found, the original function is executed, its result is stored in the cache (with a configurable Time-To-Live, TTL), and then returned.
*   **`@remove(func)`**:
    *   This decorator can be used to explicitly invalidate a specific cache entry.
    *   When the decorated function is called, it removes the cache entry corresponding to the function's arguments. This is useful when the underlying data has changed.

### Example Usage

The caching mechanism is actively used in the `auth` module to cache user details:

```python
# From auth/routes.py
from . import authCache # Assuming authCache is an instance of Cached

@authRouter.get("/me", response_model=schemas.UserRead)
@authCache.cached # Applying the caching decorator
def get_me(current_user=Depends(dependencies.get_current_user)):
    return schemas.UserRead(
        id=current_user.id, email=current_user.email, is_active=current_user.is_active
    )
```

## Integration with Other Modules

*   **`configurations/redis.py`**: Provides the configuration details for connecting to the Redis server, which are loaded by the `CacheManager`.
*   **`auth/routes.py`**: Utilizes the `@authCache.cached` decorator to cache the results of the `/auth/me` endpoint, reducing database load for frequently accessed user profiles.
