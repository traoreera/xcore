# Utilisation des Services

XCore fournit un ensemble de services de base hautement performants, accessibles uniformément par tous les plugins.

## Accès aux Services

Chaque plugin peut accéder aux services via la méthode `self.get_service(name)`.

```python
from xcore.sdk import TrustedBase

class MyPlugin(TrustedBase):
    async def on_load(self):
        # Récupération des services de base
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.scheduler = self.get_service("scheduler")
```

## Service de Base de Données (`db`)

Le service DB supporte plusieurs backends (PostgreSQL, MySQL, SQLite) et propose une API synchrone et asynchrone via SQLAlchemy.

### Utilisation Synchrone (Session)
Idéal pour les opérations complexes ou les plugins tournant dans des threads séparés.

```python
with self.db.session() as session:
    result = session.execute("SELECT name FROM users WHERE id = :id", {"id": 1})
    user_name = result.scalar()
```

### Utilisation Asynchrone
Pour une performance maximale dans les handlers `async`.

```python
async with self.db.connection() as conn:
    result = await conn.execute("SELECT * FROM products")
    products = result.fetchall()
```

## Service de Cache (`cache`)

Basé sur Redis (ou mémoire en local), ce service permet de stocker des données temporaires de manière extrêmement rapide.

### Opérations de base

```python
# Stockage avec durée de vie (TTL) en secondes
await self.cache.set("user:123:session", session_data, ttl=3600)

# Récupération
data = await self.cache.get("user:123:session")

# Suppression
await self.cache.delete("user:123:session")
```

### Optimisation : Batching
Pour réduire les allers-retours réseau, utilisez les méthodes groupées :

```python
# Récupère plusieurs clés en une seule commande (MGET)
values = await self.cache.mget(["key1", "key2", "key3"])

# Stockage groupé (Pipeline)
await self.cache.mset({
    "key1": "val1",
    "key2": "val2"
}, ttl=300)
```

## Service de Planification (`scheduler`)

Permet d'exécuter des tâches de fond de manière récurrente ou différée.

### Tâches récurrentes (Interval)

```python
self.scheduler.add_job(
    func=self.cleanup_temp_files,
    trigger="interval",
    hours=24,
    id="cleanup_job"
)
```

### Tâches différées (Date)

```python
from datetime import datetime, timedelta

run_at = datetime.now() + timedelta(minutes=30)
self.scheduler.add_job(
    func=self.send_reminder,
    trigger="date",
    run_date=run_at,
    args=[user_id]
)
```

## Services Personnalisés (Extensions)

Vous pouvez enregistrer vos propres services pour les rendre disponibles à d'autres plugins.

```python
# Dans un plugin fournisseur de service
class MyServiceProvider(TrustedBase):
    async def on_load(self):
        # Enregistre un service sous le namespace 'ext'
        self.ctx.services.register("ext.email_client", MyEmailClient())
```

## Monitoring et Santé des Services

Vous pouvez vérifier l'état des services via la CLI :
```bash
xcore services status
```

Ou par programmation dans un plugin :
```python
health = self.get_service("db").health()
if health["status"] != "ok":
    logger.error("La base de données est instable")
```

## Bonnes Pratiques

1. **Fail-Closed** : Gérez toujours les exceptions de service (perte de connexion DB, timeout Redis).
2. **Gestion des Ressources** : Utilisez toujours les gestionnaires de contexte (`with`, `async with`) pour libérer les connexions.
3. **Namespacing** : Dans le cache, préfixez vos clés avec le nom de votre plugin (ex: `my_plugin:key`) pour éviter les collisions.
