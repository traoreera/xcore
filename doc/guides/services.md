# Services

XCore expose trois services partagés via le `ServiceContainer` : **Base de données**, **Cache** et **Scheduler**. Tous sont accessibles depuis `self.get_service(name)` dans un plugin `TrustedBase`.

---

## Service Container

```python
# Accès typé depuis un plugin
self.db        = self.get_service("db")        # → AsyncSQLAdapter
self.cache     = self.get_service("cache")     # → CacheService
self.scheduler = self.get_service("scheduler") # → SchedulerService

# Connexion nommée avec type explicite
from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
self.analytics = self.get_service_as("analytics", AsyncSQLAdapter)
```

---

## Base de données

### Configuration `xcore.yaml`

```yaml
services:
  databases:
    # Connexion principale (accessible via self.get_service("db"))
    db:
      type: sqlasync          # sqlasync | sql | redis | mongodb
      url: postgresql+asyncpg://user:pass@localhost/mydb
      pool_size: 5
      max_overflow: 10
      echo: false

    # Connexion secondaire (accessible via self.get_service("analytics"))
    analytics:
      type: sqlasync
      url: postgresql+asyncpg://user:pass@analytics-host/metrics

    # Redis comme base de données (clé/valeur)
    redis_db:
      type: redis
      url: redis://localhost:6379/0
      max_connections: 50
```

Types supportés :

| `type` | Adaptateur | Usage |
|:-------|:-----------|:------|
| `sqlasync` | `AsyncSQLAdapter` | PostgreSQL, MySQL, SQLite (async) |
| `sql` | `SQLAdapter` | SQLAlchemy synchrone |
| `redis` | `RedisAdapter` | Redis key/value |
| `mongodb` | `MongoDBAdapter` | MongoDB |

### Utilisation (SQLAlchemy async)

```python
async def on_load(self):
    self.db = self.get_service("db")

@action("get_users")
async def get_users(self, payload: dict) -> dict:
    async with self.db.session() as session:
        from sqlalchemy import select
        result = await session.execute(select(User))
        users = result.scalars().all()
    return ok(users=[u.to_dict() for u in users])
```

### Migrations Alembic

XCore intègre Alembic pour les migrations. Configurer `alembic.ini` normalement, le `DATABASE_URL` peut être surchargé via `XCORE__SERVICES__DATABASES__DB__URL`.

---

## Cache

### Configuration

```yaml
services:
  cache:
    backend: memory       # memory | redis
    ttl: 300              # TTL par défaut en secondes
    max_size: 1000        # Taille max (memory uniquement)
    url: redis://localhost:6379/0   # Requis si backend=redis
```

### API

```python
async def on_load(self):
    self.cache = self.get_service("cache")

@action("get_profile")
async def get_profile(self, payload: dict) -> dict:
    key = f"profile:{payload['user_id']}"

    # Lecture
    cached = await self.cache.get(key)
    if cached:
        return ok(profile=cached, from_cache=True)

    # Écriture avec TTL custom
    profile = await self._fetch_profile(payload["user_id"])
    await self.cache.set(key, profile, ttl=600)
    return ok(profile=profile)

@action("invalidate")
async def invalidate(self, payload: dict) -> dict:
    await self.cache.delete(f"profile:{payload['user_id']}")
    return ok()

@action("batch_prime")
async def batch_prime(self, payload: dict) -> dict:
    # Opérations batch — toujours préférer mset/mget (44-77x plus rapide sur Redis)
    data = {"key:1": "val1", "key:2": "val2", "key:3": "val3"}
    await self.cache.mset(data)

    values = await self.cache.mget(list(data.keys()))
    return ok(values=values)
```

API complète :

| Méthode | Description |
|:--------|:------------|
| `get(key)` | Lit une valeur |
| `set(key, value, ttl=None)` | Écrit une valeur |
| `delete(key)` | Supprime une clé |
| `clear()` | Vide le cache entier |
| `mget(keys)` | Lit plusieurs clés en une opération |
| `mset(mapping)` | Écrit plusieurs clés en une opération |

> **Performance** : avec Redis (réseau ~2 ms), `mset`/`mget` sur 100 clés est **44–77× plus rapide** que les appels séquentiels. Voir [Benchmarks](../reference/benchmarks.md).

---

## Scheduler

### Configuration

```yaml
services:
  scheduler:
    enabled: true
    backend: memory       # memory | redis | database
    timezone: Europe/Paris

    # Jobs statiques (optionnel — les plugins peuvent en ajouter dynamiquement)
    jobs:
      - id: cleanup
        func: myapp.tasks:cleanup
        trigger: cron
        hour: 3
        minute: 0
```

Backends :

| Backend | Persistance | Usage |
|:--------|:------------|:------|
| `memory` | Non — perdu au redémarrage | Développement |
| `redis` | Oui — via Redis | Production |
| `database` | Oui — via SQLAlchemy | Production sans Redis |

### Utilisation depuis un plugin

```python
async def on_load(self):
    self.scheduler = self.get_service("scheduler")

    # Cron : tous les jours à 3h
    @self.scheduler.cron("0 3 * * *")
    async def nightly_cleanup():
        await self._cleanup()

    # Interval
    self.scheduler.add_job(
        self._sync_data,
        trigger="interval",
        minutes=5,
        id="sync_data",
        replace_existing=True,
    )

    # One-shot (date précise)
    from datetime import datetime, timedelta
    self.scheduler.add_job(
        self._send_reminder,
        trigger="date",
        run_date=datetime.now() + timedelta(hours=1),
        id="reminder_once",
    )

async def _sync_data(self):
    # Exécuté toutes les 5 minutes
    pass
```

---

## Extensions (services custom)

Pour enregistrer un service tiers dans le conteneur :

```yaml
services:
  extensions:
    stripe:
      api_key: "${STRIPE_KEY}"
      webhook_secret: "${STRIPE_WEBHOOK_SECRET}"
```

```python
# Dans un plugin "stripe_plugin"
async def on_load(self):
    cfg = self.ctx.config.services.extensions.get("stripe", {})
    self._client = StripeClient(api_key=cfg["api_key"])
    # Enregistrer dans le container pour les autres plugins
    self.ctx.services.register("stripe", self._client)
```
