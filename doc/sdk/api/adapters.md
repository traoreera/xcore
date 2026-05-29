---
title: DB Adapters
description: BaseAsyncRepository, BaseSyncRepository, BaseMongoRepository, and BaseRedisRepository.
icon: material/database-outline
---

# DB Adapters

xcoreSDK provides four ready-to-subclass repository base classes covering the most common persistence backends.

```python
from xcore.sdk import (
    BaseAsyncRepository,   # SQLAlchemy async
    BaseSyncRepository,    # SQLAlchemy sync
    BaseMongoRepository,   # Motor (async MongoDB)
    BaseRedisRepository,   # aioredis / redis-py async
)
```

---

## BaseAsyncRepository

SQLAlchemy async repository. Subclass and provide an ORM model class.

```python
from xcore.sdk import BaseAsyncRepository
from myapp.models import UserModel

class UserRepository(BaseAsyncRepository):
    def __init__(self):
        super().__init__(UserModel)
```

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_by_id` | `(id) → Model \| None` | Fetch a single row by primary key |
| `get_all` | `(filter=None, limit=0) → list[Model]` | Fetch all rows, optional filter dict |
| `create` | `(data: dict) → Model` | Insert and return the new row |
| `update` | `(id, data: dict) → Model \| None` | Update fields by primary key |
| `delete` | `(id) → bool` | Delete row by primary key |
| `count` | `(filter=None) → int` | Row count with optional filter |
| `exists` | `(filter: dict) → bool` | Check row existence |

All methods are `async`. The session is managed internally via `async with session_factory() as session`.

---

## BaseSyncRepository

Identical API to `BaseAsyncRepository` but synchronous. Suitable for scripts and non-async contexts.

```python
from xcore.sdk import BaseSyncRepository

class OrderRepository(BaseSyncRepository):
    def __init__(self):
        super().__init__(OrderModel)

repo = OrderRepository()
order = repo.get_by_id(42)
```

---

## BaseMongoRepository

Motor-based async MongoDB repository. Subclass and set `collection_name`.

```python
from xcore.sdk import BaseMongoRepository

class LogRepository(BaseMongoRepository):
    collection_name = "logs"

    def __init__(self, db):
        super().__init__(db)   # db: AsyncIOMotorDatabase
```

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_by_id` | `(id: str) → dict \| None` | Find by `_id` (auto-converts to `ObjectId`) |
| `get_all` | `(filter=None, limit=0) → list[dict]` | Find many |
| `find_one` | `(filter: dict) → dict \| None` | Find one by arbitrary filter |
| `create` | `(data: dict) → dict` | Insert one, returns the inserted document |
| `update` | `(id: str, data: dict) → dict \| None` | `$set` update by `_id` |
| `delete` | `(id: str) → bool` | Delete by `_id` |
| `count` | `(filter=None) → int` | Document count |
| `exists` | `(filter: dict) → bool` | Check document existence |

`_id` fields are automatically serialized to/from `str`.

---

## BaseRedisRepository

Async Redis repository with JSON serialization. Subclass and set `prefix` to namespace your keys.

```python
from xcore.sdk import BaseRedisRepository

class SessionRepository(BaseRedisRepository):
    prefix = "session"

    def __init__(self, redis):
        super().__init__(redis)  # redis: aioredis.Redis or redis.asyncio.Redis
```

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get` | `(key: str) → Any \| None` | JSON-deserialize value at `prefix:key` |
| `set` | `(key: str, value: Any, ttl=None) → None` | JSON-serialize and store |
| `delete` | `(key: str) → bool` | Delete a key |
| `exists` | `(key: str) → bool` | Check key existence |
| `expire` | `(key: str, seconds: int) → None` | Set TTL on existing key |
| `ttl` | `(key: str) → int` | Remaining TTL in seconds |
| `keys` | `(pattern="*") → list[str]` | Keys matching pattern under prefix |
| `mget` | `(keys: list[str]) → list[Any]` | Batch get |
| `mset` | `(mapping: dict, ttl=None) → None` | Batch set |

All keys are automatically prefixed: `{prefix}:{key}`.

!!! note "Serialization"
    Values are JSON-serialized on `set` and deserialized on `get`. Non-JSON-serializable types will raise `TypeError`.
