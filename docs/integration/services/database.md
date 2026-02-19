# database.py (Database Manager)

Le fichier `database.py` dans le module `integration/services` gère toutes les connexions aux bases de données configurées dans `integration.yaml`.

## Rôle

Le `DatabaseManager` est le point d'accès centralisé pour interagir avec plusieurs bases de données (SQL, NoSQL, Redis). Il offre une interface unifiée pour :
- Initialiser toutes les connexions configurées (SQLite, PostgreSQL, MySQL, Redis, MongoDB).
- Gérer les adaptateurs spécifiques à chaque type de base de données.
- Fournir des sessions SQL via des gestionnaires de contexte (`contextmanager`).
- Gérer l'arrêt propre des connexions.

## Structure du module

### `DatabaseManager`

Le gestionnaire principal de toutes les bases de données.

```python
class DatabaseManager:
    def __init__(self, config: IntegrationConfig):
        ...
    def init_all(self):
        ...
    def get(self, name: str = "default") -> Any:
        ...
    def session(self, name: str = "default") -> Iterator:
        ...
    def close_all(self):
        ...
```

### Adaptateurs

Chaque type de base de données possède son propre adaptateur interne :
- `SQLAdapter` (SQLAlchemy) : Pour SQLite, PostgreSQL, MySQL.
- `AsyncSQLAdapter` (SQLAlchemy async) : Pour PostgreSQL (asyncpg), MySQL (aiomysql).
- `RedisAdapter` (redis-py) : Pour Redis.
- `MongoAdapter` (pymongo) : Pour MongoDB.

## Exemple d'utilisation

```python
from xcore.integration.services.database import DatabaseManager

# Initialisation (généralement via Integration.init())
db_manager = DatabaseManager(config)
db_manager.init_all()

# Accès à une session SQL
with db_manager.session("default") as db:
    # 'db' est une session SQLAlchemy
    users = db.query(User).all()

# Accès direct à l'adaptateur
redis_adapter = db_manager.get("cache_redis")
redis_adapter.client.set("key", "value")
```

## Détails Techniques

- Le mapping entre le type de BDD dans le YAML et l'adaptateur est défini dans `_ADAPTER_MAP`.
- Les adaptateurs sont instanciés à la demande ou lors de `init_all()`.
- Les dépendances tierces (SQLAlchemy, pymongo, redis-py) sont importées conditionnellement dans les adaptateurs.

## Contribution

- Pour ajouter un nouveau type de base de données (ex: `Neo4j`, `Cassandra`), créez un nouvel adaptateur et enregistrez-le dans `_ADAPTER_MAP`.
- Chaque adaptateur doit implémenter au minimum une méthode `init()` et `close()`.
- Assurez-vous que les méthodes `session()` sont sûres et ferment toujours la connexion, même en cas d'erreur.
