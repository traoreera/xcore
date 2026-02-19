# redis.py

Le fichier `redis.py` définit la classe `Rediscfg`, responsable de la configuration du service Redis.

## Rôle

La classe `Rediscfg` cible la section `"xcore"` (nom historique) du fichier `config.json`. Elle gère des paramètres essentiels pour le bon fonctionnement de Redis :
- L'hôte et le port de connexion à Redis.
- Le numéro de base de données (db).
- Le délai de vie (TTL) par défaut pour les données.

## Structure de `Rediscfg`

```python
class Rediscfg(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "xcore")
        ...
```

### Paramètres `default_migration` (Redis)

Si la section n'est pas présente dans le fichier JSON, les valeurs suivantes sont utilisées :
- `host`: `localhost`
- `port`: `6379`
- `db`: `0`
- `TTL`: `60`

## Exemple d'utilisation

```python
from xcore.configurations.redis import Rediscfg
from xcore.configurations.base import Configure

# Initialisation
redis_cfg = Rediscfg(conf=Configure())

# Accès aux paramètres de connexion
host = redis_cfg.custom_config["host"]
port = redis_cfg.custom_config["port"]

# Accès au TTL par défaut
ttl = redis_cfg.custom_config["TTL"]
```

## Détails Techniques

- `Redis`: Un `TypedDict` qui définit la structure complexe de la configuration de Redis.
- `custom_config`: Cette propriété contient le dictionnaire de configuration final pour Redis.

## Contribution

- Pour modifier les paramètres de connexion par défaut à Redis, modifiez le dictionnaire `default_migration` dans le constructeur de `Rediscfg`.
- Si vous modifiez le TTL par défaut, assurez-vous que les nouvelles valeurs ne cassent pas la cohérence des données pour les clients existants.
