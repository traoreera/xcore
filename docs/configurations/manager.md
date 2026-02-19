# manager.py (Configuration)

Le fichier `manager.py` dans le module `configurations` définit la classe `ManagerCfg`, responsable de la configuration du Plugin Manager et du système de snapshots.

## Rôle

La classe `ManagerCfg` cible la section `"migration"` (nom historique) du fichier `config.json`. Elle gère des paramètres essentiels pour le bon fonctionnement des plugins :
- Le répertoire des plugins et l'intervalle de surveillance.
- La configuration des tâches en arrière-plan (background tasks).
- Les extensions et fichiers à ignorer lors des snapshots (snapshots).

## Structure de `ManagerCfg`

```python
class ManagerCfg(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "migration")
        ...
```

### Paramètres `default_migration` (ManagerType)

Si la section n'est pas présente dans le fichier JSON, les valeurs suivantes sont utilisées :
- `dotenv`: `./manager/.env`
- `plugins`: `{"directory": "./plugins", "interval": 2, "entry_point": "run"}`
- `tasks`: `{"directory": "./backgroundtask", "default": "./manager/plTask.py", "auto_restart": True, "interval": 2, "max_retries": 3}`
- `snapshot`: Contient une liste d'extensions (`.log`, `.pyc`, etc.) et de noms de fichiers (`__pycache__`, `.git`, etc.) à ignorer lors de la surveillance des changements.

## Exemple d'utilisation

```python
from xcore.configurations.manager import ManagerCfg
from xcore.configurations.base import Configure

# Initialisation
manager_cfg = ManagerCfg(conf=Configure())

# Accès au répertoire des plugins
plugins_dir = manager_cfg.custom_config["plugins"]["directory"]

# Accès aux fichiers ignorés par le snapshot
ignored_files = manager_cfg.custom_config["snapshot"]["filenames"]
```

## Détails Techniques

- `ManagerType`: Un `TypedDict` qui définit la structure complexe de la configuration du manager.
- `SnapshotType`: Un `TypedDict` pour configurer le système de snapshots utilisé par le watcher de `Manager`.

## Contribution

- Pour ajouter un nouveau type de fichier à ignorer lors de la surveillance des plugins, modifiez la liste `snapshot` dans le constructeur de `ManagerCfg`.
- Si vous modifiez le point d'entrée par défaut des plugins (`entry_point`), assurez-vous que les plugins existants sont compatibles avec cette modification.
