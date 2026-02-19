# registry.py (Service Registry)

Le fichier `registry.py` dans le module `integration/core` fournit le registre de services de xcore pour l'injection de dépendances.

## Rôle

Le `ServiceRegistry` est le catalogue central de toutes les instances de services (DB, Cache, Scheduler) de xcore. Il fournit une interface simple pour enregistrer et récupérer des services par leur nom.

## Structure de la classe `ServiceRegistry`

```python
class ServiceRegistry:
    def __init__(self):
        self._services: Dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        ...

    def get(self, name: str) -> Any:
        ...

    def all(self) -> Dict[str, Any]:
        ...
```

### Méthodes Clés

- `register(name, service)`: Ajoute une instance de service au registre sous un nom unique.
- `get(name)`: Récupère l'instance du service par son nom. Lève une `KeyError` si non trouvé.
- `all()`: Retourne un dictionnaire contenant tous les services enregistrés.
- `exists(name)`: Vérifie si un service est présent dans le registre.
- `clear()`: Vide le registre (utile pour les tests).

## Exemple d'utilisation

```python
from xcore.integration.core.registry import get_registry

registry = get_registry()

# Enregistrer un service
registry.register("db", my_database_instance)

# Récupérer un service
db = registry.get("db")

# Vérifier si un service existe
if registry.exists("cache"):
    cache = registry.get("cache")
```

## Détails Techniques

- `ServiceRegistry` est géré comme un singleton global via `get_registry()`.
- Les services peuvent être n'importe quel type d'objet Python (classes de base `BaseService` ou objets tiers).
- Il n'y a pas de vérification de type lors de l'enregistrement ; le nom doit être unique.

## Contribution

- Le registre doit rester simple ; ne lui ajoutez pas de logique de cycle de vie (utilisez `Integration` pour cela).
- Assurez-vous que l'accès au registre est thread-safe si nécessaire (bien que xcore soit principalement `asyncio`).
- Documentez les noms de services standard (ex: `db`, `cache`, `scheduler`) pour garantir la cohérence dans le framework.
