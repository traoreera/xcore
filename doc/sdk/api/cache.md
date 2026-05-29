---
title: Cache Decorators
description: "@cached and @invalidate decorators for transparent result caching."
icon: material/cached
---

# Cache

xcoreSDK provides two decorators for transparent result caching: `@cached` to store handler results and `@invalidate` to evict stale entries.

```python
from xcore.sdk import cached, invalidate
```

Both decorators work with any cache service registered as `"cache"` in `self.ctx.services`. They no-op silently when the service is absent.

---

## @cached

Caches the return value of an async action handler.

```python
from xcore.sdk import cached

@action("get_user")
@cached(ttl=300, key=lambda self, p: f"user:{p['id']}")
async def get_user(self, payload: dict) -> dict:
    # Only runs on cache miss
    user_id = payload["id"]
    ...
    return ok(user=user)
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `ttl` | `int \| None` | `None` | Time-to-live in seconds; `None` = no expiry |
| `key` | `callable \| str \| None` | `None` | Cache key strategy (see below) |

### Key strategies

**Callable** (recommended):
```python
@cached(ttl=300, key=lambda self, p: f"user:{p['id']}")
```

**String** — used as-is (static key, shared across all callers):
```python
@cached(ttl=60, key="config:global")
```

**None** — auto-generates a SHA-256 hash of `(plugin_name, method_name, payload)`:
```python
@cached(ttl=30)  # key derived from payload
```

### Behavior

1. Compute cache key
2. `cache.get(key)` → return cached value on hit
3. On miss: call the handler, store result with `cache.set(key, result, ttl=ttl)`
4. Return result

If `self.ctx` is `None` or the `"cache"` service is not registered, the handler is called directly with no caching.

---

## @invalidate

Evicts a cache entry after the handler executes. Used to keep caches consistent after mutations.

```python
from xcore.sdk import invalidate

@action("update_user")
@invalidate(key=lambda self, p: f"user:{p.get('id', '')}")
async def update_user(self, payload: dict) -> dict:
    # cache eviction happens after this returns
    ...
    return ok(updated=True)
```

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `key` | `callable \| str` | Same key strategies as `@cached` |

Eviction happens **after** the handler returns (success or failure). If the key does not exist, the operation is a no-op.

---

## Combining @cached and @invalidate

A common pattern: cache reads, invalidate on writes:

```python
@action("get_user")
@cached(ttl=300, key=lambda self, p: f"user:{p['id']}")
async def get_user(self, payload: dict) -> dict:
    ...

@action("update_user")
@invalidate(key=lambda self, p: f"user:{p.get('id', '')}")
async def update_user(self, payload: dict) -> dict:
    ...

@action("create_user")
@invalidate(key=lambda self, p: f"user:{p.get('id', '')}")
async def create_user(self, payload: dict) -> dict:
    ...
```

---

## Manual cache access

For cache operations not covered by the decorators:

```python
cache = self.get_service("cache")

await cache.get("my:key")
await cache.set("my:key", value, ttl=60)
await cache.delete("my:key")
await cache.keys("my:*")     # glob pattern
await cache.clear()          # flush all (use with care)
```

---

## Backend configuration

The cache backend is configured in the kernel, not in the plugin. Switching between in-memory and Redis requires no plugin code changes — the same `@cached` API works on both.

| Backend | Use case |
|---------|----------|
| In-memory (`dict`) | Development, single-process |
| Redis | Production, multi-process, distributed TTL |
