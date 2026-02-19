# plugins.py (Configuration)

Le fichier `plugins.py` dans le module `configurations` définit la classe `PluginsConfig`, responsable de la configuration des plugins.

## Rôle

La classe `PluginsConfig` cible la section `"plugins"` du fichier `config.json`. Elle gère des paramètres essentiels pour le bon fonctionnement des plugins :
- Le nom et le chemin de chaque plugin.

## Structure de `PluginsConfig`

```python
class PluginsConfig(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "plugins")
        ...
```

### Paramètres `default_migration` (PluginsType)

Si la section n'est pas présente dans le fichier JSON, les valeurs suivantes sont utilisées :
- `default`: `{}`

## Exemple d'utilisation

```python
from xcore.configurations.plugins import PluginsConfig
from xcore.configurations.base import Configure

# Initialisation
plugins_cfg = PluginsConfig(conf=Configure())

# Accès à la configuration d'un plugin
plugin_config = plugins_cfg.custom.get("my_plugin")

if plugin_config:
    print(plugin_config["path"])
```

## Détails Techniques

- `PluginsPEs`: Un `TypedDict` qui définit la structure de base pour la configuration d'un plugin (`name` et `path`).
- `custom`: Contient le dictionnaire de configuration final pour les plugins.

## Contribution

- Pour ajouter une nouvelle configuration de plugin par défaut, modifiez le dictionnaire `default` dans le constructeur de `PluginsConfig`.
- Si vous modifiez la structure de `PluginsPEs`, assurez-vous de mettre à jour le code qui consomme ces paramètres dans le module `sandbox`.
