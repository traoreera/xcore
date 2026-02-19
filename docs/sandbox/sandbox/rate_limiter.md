# rate_limiter.py

Le fichier `xcore/sandbox/sandbox/rate_limiter.py` gère le quota d’appels par plugin (fenêtre glissante).

## Classes

- `RateLimiter`
- `RateLimiterRegistry`
- `RateLimitExceeded`

## API

- `RateLimiter.check(plugin_name)`
- `RateLimiter.stats()`
- `RateLimiterRegistry.register(plugin_name, config)`
- `RateLimiterRegistry.check(plugin_name)`

## Contribution

- Maintenir les accès thread-safe via `asyncio.Lock`.
- Garder la logique O(n) sur deque courte (purge timestamps).
