# Services

XCore expose cinq services partagés via le `ServiceContainer` : **Base de données**, **Cache**, **Scheduler**, **XWorker (Celery)** et **Extensions**. Tous sont accessibles depuis `self.get_service(name)` dans un plugin `TrustedBase`.

---

## Service Container

```python
# Accès typé depuis un plugin
self.db        = self.get_service("db")        # → AsyncSQLAdapter
self.cache     = self.get_service("cache")     # → CacheService
self.scheduler = self.get_service("scheduler") # → SchedulerService
self.worker    = self.get_service("worker")    # → WorkerService

# Connexion nommée avec type explicite
from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
self.analytics = self.get_service_as("analytics", AsyncSQLAdapter)
```

---

## Base de données

### Configuration

```yaml
services:
  databases:
    db:
      type: sqlasync
      url: postgresql+asyncpg://user:pass@localhost/mydb
      pool_size: 5
      max_overflow: 10
      echo: false

    analytics:
      type: sqlasync
      url: postgresql+asyncpg://user:pass@analytics-host/metrics

    redis_db:
      type: redis
      url: redis://localhost:6379/0
      max_connections: 50
```

| `type` | Adaptateur | Usage |
|:-------|:-----------|:------|
| `sqlasync` | `AsyncSQLAdapter` | PostgreSQL, MySQL, SQLite (async) |
| `sql` | `SQLAdapter` | SQLAlchemy synchrone |
| `redis` | `RedisAdapter` | Redis key/value |
| `mongodb` | `MongoDBAdapter` | MongoDB |

### Utilisation

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

---

## Cache

### Configuration

```yaml
services:
  cache:
    backend: redis        # memory | redis
    url: redis://localhost:6379/0
    ttl: 300
    max_size: 1000        # ignoré si backend=redis
```

### API

```python
async def on_load(self):
    self.cache = self.get_service("cache")

@action("get_profile")
async def get_profile(self, payload: dict) -> dict:
    key = f"profile:{payload['user_id']}"
    cached = await self.cache.get(key)
    if cached:
        return ok(profile=cached, from_cache=True)

    profile = await self._fetch_profile(payload["user_id"])
    await self.cache.set(key, profile, ttl=600)
    return ok(profile=profile)
```

| Méthode | Description |
|:--------|:------------|
| `get(key)` | Lit une valeur |
| `set(key, value, ttl=None)` | Écrit une valeur |
| `delete(key)` | Supprime une clé |
| `clear()` | Vide le cache entier |
| `mget(keys)` | Lit plusieurs clés en une opération |
| `mset(mapping)` | Écrit plusieurs clés en une opération |

> **Performance** : `mset`/`mget` sur 100 clés Redis est **44–77× plus rapide** que les appels séquentiels. Voir [Benchmarks](../reference/benchmarks.md).

---

## Scheduler

### Configuration

```yaml
services:
  scheduler:
    enabled: true
    backend: redis        # memory | redis | database
    timezone: Europe/Paris
    jobs:
      - id: cleanup
        func: myapp.tasks:cleanup
        trigger: cron
        hour: 3
        minute: 0
```

### Utilisation

```python
async def on_load(self):
    self.scheduler = self.get_service("scheduler")

    @self.scheduler.cron("0 3 * * *")
    async def nightly_cleanup():
        await self._cleanup()

    self.scheduler.add_job(
        self._sync_data,
        trigger="interval",
        minutes=5,
        id="sync_data",
        replace_existing=True,
    )
```

---

## XWorker (Celery)

Service de traitement asynchrone de tâches basé sur Celery.

### Configuration

```yaml
services:
  xworker:
    enabled: true
    name: "mon-app"
    broker_url: redis://localhost:6379/0
    result_backend: redis://localhost:6379/1
    task_default_queue: default
    concurrency: 4
    task_soft_time_limit: 300     # SoftTimeLimitExceeded après 300s
    task_time_limit: 360          # kill forcé après 360s
    task_serializer: json
    result_serializer: json
    accept_content: [json]
    result_expires: 86400         # conservation 24h
    broker_connection_retry_on_startup: true
    queues:
      - default
      - emails
    modules:
      - myapp.tasks.emails        # modules chargés au démarrage
      - myapp.tasks.reports
```

### Déclarer une tâche

```python
from xcore.services.xworker import task

@task(name="emails.send_welcome", queue="emails", bind=True, max_retries=3)
def send_welcome_email(self, user_id: int, **kwargs):
    try:
        # logique d'envoi...
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### Envoyer une tâche depuis un plugin

```python
async def on_load(self):
    self.worker = self.get_service("worker")

@action("register")
async def register(self, payload: dict) -> dict:
    user = await self._create_user(payload)

    # Envoi asynchrone — non bloquant
    self.worker.send(
        "emails.send_welcome",
        user_id=user.id,
        queue="emails",
    )
    return ok(user_id=user.id)
```

### Vérifier le résultat

```python
result = self.worker.get_result(task_id)
if result.ready():
    print(result.get())
```

### Lancer le worker

```bash
xcore worker start celery
xcore worker start celery -Q default,emails -c 8 --detach
xcore worker beat --detach     # scheduler Celery Beat
xcore worker inspect            # tâches et workers actifs
```

---

## Extensions (services custom)

```yaml
services:
  extensions:
    stripe:
      module: myapp.services.stripe:StripeService
      config:
        api_key: "${STRIPE_KEY}"
```

```python
async def on_load(self):
    stripe = self.get_service("ext.stripe")
```
