# cache.py (CacheService)

Le fichier `xcore/integration/services/cache.py` fournit un cache unifié mémoire/Redis.

## Backends

- `MemoryBackend` (TTL + eviction FIFO)
- `RedisBackend` (serialization `pickle`)

## API publique

- `init()`
- `get(key, default=None)`
- `set(key, value, ttl=None)`
- `delete(key)`
- `exists(key)`
- `clear()`
- `get_or_set(key, factory, ttl=None)`
- `cached(ttl=None, key=None)` (décorateur)

## Exemple

```python
cache.set("user:42", {"id": 42}, ttl=120)
user = cache.get("user:42")

@cache.cached(ttl=60, key="profile:{user_id}")
def get_profile(user_id: int):
    return {"id": user_id}
```

## Contribution

- Vérifier la sécurité de sérialisation (pickle) selon vos contraintes.
- Ajouter un backend alternatif si besoin (ex: Memcached).
