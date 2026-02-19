# loader.py (Config Loader)

Le fichier `loader.py` dans le module `integration/config` est responsable du chargement et de la résolution de la configuration de xcore définie dans `integration.yaml`.

## Rôle

Le `ConfigLoader` est le cerveau derrière le chargement de la configuration de xcore. Son rôle est de :
- Charger et parser le fichier `integration.yaml`.
- Gérer l'ordre de résolution des variables de configuration (substitution des variables d'environnement `${VAR}`).
- Injecter automatiquement le contenu du fichier `.env` si demandé.
- Surcharger la configuration YAML via des variables d'environnement de type `INTEGRATION__SECTION__KEY`.
- Parser les données brutes YAML en dataclasses typées (`IntegrationConfig`, `DatabaseConfig`, etc.) pour une utilisation facile dans le code.

## Structure du module

### `IntegrationConfig`

Définit la structure typée de la configuration complète de xcore.

```python
class IntegrationConfig:
    app: AppConfig
    extensions: Dict[str, ExtensionConfig]
    databases: Dict[str, DatabaseConfig]
    cache: CacheConfig
    scheduler: SchedulerConfig
    logging: LoggingConfig
    raw: Dict[str, Any]
```

### `ConfigLoader`

La classe responsable du chargement physique.

#### Méthodes Clés

- `classmethod load(path=None)`: Charge le fichier `integration.yaml` et retourne une instance `IntegrationConfig`.
- `_handle_dotenv(raw)`: Charge le fichier `.env` si `env_variable.inject: true` est présent dans le YAML.
- `_resolve_env(raw)`: Remplace récursivement toutes les occurrences de `${VAR}` par la valeur de la variable d'environnement `VAR`.
- `_apply_env_overrides(raw)`: Applique les surcharges `INTEGRATION__SECTION__KEY=val` (ex: `INTEGRATION__APP__ENV=production`).
- `_parse(raw)`: Convertit les dictionnaires bruts en dataclasses (`AppConfig`, `DatabaseConfig`, etc.).

## Exemple d'utilisation

```python
from xcore.integration.config.loader import get_config

# Charge la configuration par défaut (integration.yaml)
config = get_config()

# Accède aux paramètres de l'application
print(config.app.name)

# Accède aux bases de données configurées
for name, db_cfg in config.databases.items():
    print(f"BDD {name}: {db_cfg.type} -> {db_cfg.url}")
```

## Détails Techniques

- Le loader recherche le fichier `integration.yaml` dans plusieurs répertoires par défaut (`.`, `config/`, `integrations/`).
- La substitution `${VAR}` est récursive et gère les valeurs par défaut `${VAR:-default}` (si implémenté).
- Les surcharges via `INTEGRATION__` sont prioritaires sur le YAML.

## Contribution

- Si vous ajoutez une nouvelle section dans `integration.yaml`, vous devez définir la `dataclass` correspondante et ajouter sa méthode de parsing (`_parse_...`).
- Assurez-vous que les types par défaut sont cohérents avec ceux du framework.
- Maintenez la compatibilité descendante lors de la modification des structures de configuration existantes.
