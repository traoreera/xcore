---
title: Cache Service
description: Unified caching interface for Xcore supporting Memory and Redis backends.
icon: material/cached
---

# Cache Service

The `CacheService` provides a unified, asynchronous interface for caching data. It abstracts the underlying storage (Memory or Redis), allowing plugins to use the same API regardless of the deployment environment.

---

### Prerequisites

- [x] [Service Container](./services.md) overview understood
- [x] `redis` driver installed (only if using the Redis backend)

---

### Key Concepts

#### Backend Abstraction
Plugins interact with the `CacheService` facade, which delegates calls to a `MemoryBackend` (standard Python dictionary with TTL), a `RedisCacheBackend`, or a `TieredCacheBackend` (memory **L1** in front of Redis **L2**).

#### Tiered (L1 + L2) Backend
`backend: tiered` reads L1 (local process memory) first — microsecond latency — and falls back to L2 (shared Redis) on miss, backfilling L1 for next time. Writes go to both layers (write-through).

```text
get("k")  →  L1 hit? return it
          →  L1 miss → L2 hit? backfill L1, return it
          →  both miss → None
```

!!! warning "Bounded cross-node staleness"
    There is no push-based invalidation between nodes (no Redis pub/sub). If node A writes a key, node B's L1 keeps serving its old value until that entry's TTL expires — L2 is always fresh, only each node's local L1 can lag. `ttl` is shared by both layers today (no separate L1/L2 TTL knob), so it directly bounds the worst-case cross-node staleness window. Use the plain `redis` backend instead if you need strict consistency.

#### Multi-Tenant Isolation
When `tenancy.isolate_cache` is enabled in `xcore.yaml`, the `CacheService` automatically prefixes every key with the current `tenant_id`. This prevents data leakage between tenants sharing the same Redis instance.

```text
# Logical Key: "user:123"
# Actual Redis Key: "tenant_A:user:123"
```

---

### Practical Guide

#### 1. Basic Operations
```python linenums="1"
from xcore import TrustedBase

class Plugin(TrustedBase):
    async def get_user_profile(self, user_id):
        cache = self.get_service("cache")

        # Get from cache
        profile = await cache.get(f"profile:{user_id}")

        if not profile:
            # Set with custom TTL (in seconds)
            profile = await self.fetch_from_db(user_id)
            await cache.set(f"profile:{user_id}", profile, ttl=3600)

        return profile
```

#### 2. The `get_or_set` Pattern
Use this pattern to simplify your caching logic. It handles the "check-fetch-set" cycle in a single call.

```python linenums="1"
async def get_settings(self):
    cache = self.get_service("cache")
    return await cache.get_or_set(
        "global_settings",
        factory=self.fetch_settings,  # (1)!
        ttl=300
    )
```

1.  `factory` can be an async function, a sync function, or a static value.

#### 3. Batch Operations
For high-performance scenarios, use `mget` and `mset` to reduce network round-trips.

```python
keys = ["price:AAPL", "price:GOOG", "price:TSLA"]
prices = await cache.mget(keys)
```

---

### API Reference

#### `CacheService` Methods
| Method | Return Type | Description |
|--------|-------------|-------------|
| `get(key)` | `Any \| None` | Retrieve a value by key. Returns `None` if expired or missing. |
| `set(key, value, ttl)`| `None` | Store a value with an optional TTL (defaults to global config). |
| `delete(key)` | `bool` | Remove a key. Returns `True` if it existed. |
| `exists(key)` | `bool` | Check if a key exists without retrieving its value. |
| `get_or_set(key, factory, ttl)`| `Any` | Returns cached value or calls `factory()` to populate it. |
| `mget(keys)` | `dict` | Retrieve multiple keys in a single operation. |
| `mset(mapping, ttl)`| `None` | Store multiple keys from a dictionary. |
| `clear()` | `None` | Wipe all keys from the cache. |

---

### YAML Configuration

```yaml linenums="1" title="xcore.yaml"
services:
  cache:
    backend: "redis"   # str — "memory" | "redis" | "tiered". Default: "memory"
    ttl: 300           # int — Global TTL in seconds. Default: 300
    max_size: 1000     # int — Max entries (memory / tiered L1). Default: 1000
    url: "redis://localhost:6379/0" # str — Required for "redis" and "tiered". Default: null
```

---

### Common Errors & Pitfalls

!!! danger "Serialization Errors"
    The Redis backend uses `pickle` or `json` (depending on configuration) to serialize Python objects. Ensure your data is serializable.
    **Check**: Complex objects with database connections or open files cannot be cached in Redis.

!!! warning "Memory Backend Volatility"
    Data in the `memory` backend is lost every time the server restarts. Use it only for transient data or small deployments.

!!! failure "Cache Stampede"
    If a very hot key expires, multiple requests might try to recompute it simultaneously. Use `get_or_set` to minimize this risk, though it does not yet include a global lock.

---

### Best Practices

!!! success "Granular TTLs"
    While a global TTL is convenient, always provide a specific `ttl` in your `set()` calls based on how often the data actually changes.

!!! tip "Use Namespacing"
    Always prefix your keys with a namespace (e.g., `user:`, `order:`) to avoid collisions between different plugins using the same cache service.
