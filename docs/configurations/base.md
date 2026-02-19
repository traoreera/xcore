# base.py

Le fichier `base.py` définit les classes de base du système de configuration de xcore.

## Classes Clés

### `Configure`

La classe `Configure` est responsable de la lecture physique du fichier de configuration JSON.

```python
class Configure:
    def __init__(self, default: str = "config.json") -> None:
        ...
    def __call__(self, conf: str) -> Optional[Dict[str, Any]]:
        ...
```

- `__init__(default)`: Charge le fichier JSON spécifié (défaut: `config.json`).
- `__call__(conf)`: Retourne une section spécifique de la configuration ou l'intégralité du dictionnaire si `"All"` est passé en paramètre.

### `BaseCfg`

La classe `BaseCfg` est la classe mère pour toutes les autres classes de configuration de xcore. Elle offre des méthodes utilitaires pour manipuler les données.

```python
class BaseCfg:
    def __init__(self, conf: Configure, section: str):
        ...
```

- `get_section()`: Retourne le dictionnaire de la section actuelle.
- `getter(key)`: Retourne la valeur associée à la clé donnée dans la section.
- `adder(key, value)`: Ajoute ou met à jour une valeur dans la section.
- `remover(key)`: Supprime une clé de la section.
- `saver()`: Sauvegarde les modifications apportées à la configuration dans le fichier JSON original.
- `printer()`: Affiche joliment le contenu de la section actuelle au format JSON.

## Exemple d'utilisation

```python
from xcore.configurations.base import Configure, BaseCfg

# 1. Charger le fichier
conf = Configure("config.json")

# 2. Utiliser BaseCfg pour une section spécifique
my_cfg = BaseCfg(conf, "my_section")

# 3. Manipuler les données
print(my_cfg.getter("api_key"))
my_cfg.adder("timeout", 30)
my_cfg.saver()
```

## Contribution

- Évitez d'ajouter des méthodes spécifiques à un module dans `BaseCfg`. Cette classe doit rester générique.
- Lors de la modification de `saver()`, assurez-vous de conserver l'indentation de 4 espaces pour garantir la lisibilité du fichier JSON.
