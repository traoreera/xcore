# Utilisation des Services XCore

Les services XCore fournissent une infrastructure technique partagée (Base de données, Cache, Planificateur de tâches) disponible pour tous les plugins.

## 1. Accès aux Services

Chaque plugin accède aux services via l'objet `ServiceContainer`. Le SDK offre deux méthodes principales :

```python
from xcore.sdk import TrustedBase

class Plugin(TrustedBase):
    async def on_load(self):
        # 1. Récupération directe (typage automatique par IDE)
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

        # 2. Récupération typée (pour connexions nommées ou extensions)
        # from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        # self.analytics = self.get_service_as("analytics", AsyncSQLAdapter)
```

---

## 2. Service de Base de Données (`db`)

XCore utilise **SQLAlchemy** (ou des adaptateurs spécifiques) pour gérer les connexions SQL (PostgreSQL, MySQL, SQLite).

### Repository SQL : `BaseSyncRepository` / `BaseAsyncRepository`

Le SDK simplifie l'accès aux données avec le pattern Repository.

```python
from xcore.sdk import BaseAsyncRepository
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)

class UserRepository(BaseAsyncRepository[User]):
    """Repository personnalisé pour les utilisateurs."""
    pass

# --- Dans votre plugin ---
class UserPlugin(TrustedBase):
    async def on_load(self):
        self.db = self.get_service("db")
        self.users = UserRepository(User)

    async def create_user(self, name: str):
        # Utilisation d'une session asynchrone
        async with self.db.session() as session:
            new_user = User(name=name)
            await self.users.create(session, new_user)
            await session.commit()
            return new_user.id
```

---

## 3. Service de Cache (`cache`)

Le service de cache supporte le stockage en **Mémoire** ou **Redis**.

```python
# Accès au service de cache
cache = self.get_service("cache")

# --- Opérations de base ---
# Stocker une valeur pendant 5 minutes (300s)
await cache.set("user_123:profile", {"name": "Alice"}, ttl=300)

# Récupérer une valeur
profile = await cache.get("user_123:profile")

# Supprimer une valeur
await cache.delete("user_123:profile")

# --- Opérations groupées (Optimisées Redis) ---
await cache.mset({"k1": "v1", "k2": "v2"})
values = await cache.mget(["k1", "k2"])
```

---

## 4. Service de Planification (`scheduler`)

XCore intègre **APScheduler** pour exécuter des tâches en arrière-plan ou de manière périodique.

```python
# Accès au planificateur
scheduler = self.get_service("scheduler")

# --- Planifier une tâche ---
# Tâche immédiate (Background Job)
await scheduler.add_job(
    self.process_data,
    args=[data_id],
    id=f"process_{data_id}"
)

# Tâche planifiée (Cron)
await scheduler.add_cron_job(
    self.daily_report,
    hour=0,
    minute=0,
    id="daily_cleanup"
)

# Tâche par intervalle
await scheduler.add_interval_job(
    self.heartbeat,
    seconds=60,
    id="ping_external_api"
)
```

---

## 5. Propagation des Services

La propagation des services permet à un plugin d'exposer des fonctionnalités à d'autres plugins de manière structurée.

### Cycle de Propagation
1. Un plugin fournisseur enregistre son service dans `on_load`.
2. Le `LifecycleManager` détecte l'enregistrement et met à jour le `ServiceContainer` global.
3. Les plugins dépendants (déclarés dans `requires`) peuvent alors accéder au nouveau service.

```python
# Plugin Fournisseur (ex: billing)
class BillingPlugin(TrustedBase):
    async def on_load(self):
        self.register_service("billing_engine", self.engine)

# Plugin Consommateur
class CartPlugin(TrustedBase):
    async def on_load(self):
        # Disponible car 'billing' est une dépendance requise
        self.billing = self.get_service("billing_engine")
```

---

## 6. Surveillance de la Santé (Health Checks)

Chaque service intégré implémente une méthode de santé. Vous pouvez consulter l'état de tous les services via :

```bash
# Via la CLI
xcore services status

# Via l'API HTTP
curl http://localhost:8082/plugin/ipc/health
```

---

## Bonnes Pratiques

1. **Lazy Initialization** : Si votre service consomme beaucoup de ressources, n'établissez la connexion réelle que lors du premier appel.
2. **Gestion des Timeouts** : Utilisez toujours des timeouts lors des appels aux services externes (DB, Redis) pour ne pas bloquer le framework.
3. **Namespacing des Clés** : Préfixez toujours vos clés de cache et IDs de jobs par le nom de votre plugin (ex: `auth:token:123`) pour éviter les collisions.
