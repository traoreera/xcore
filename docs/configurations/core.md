# core.py

Le fichier `core.py` contient la classe `Xcorecfg`, responsable de la configuration globale de l'application xcore.

## Rôle

La classe `Xcorecfg` hérite de `BaseCfg` et cible la section `"xcore"` du fichier `config.json`. Elle contient des configurations critiques telles que :
- Les paramètres de journalisation (logs).
- Les URL de bases de données par défaut.
- Les extensions (modules internes) actives.
- Les dépendances de fichiers système.
- La configuration des middlewares de sécurité.

## Structure de `Xcorecfg`

```python
class Xcorecfg(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "xcore")
        ...
```

### Paramètres `default_migration`

Si la section `"xcore"` est absente du fichier JSON, les valeurs suivantes sont utilisées :
- `logs`: `{"console": True, "file": "app.log"}`
- `data`: `{"url": "sqlite:///test.db", "echo": False}`
- `extensions`: Liste des extensions par défaut (`auth`, `data`, `manager`, etc.).
- `midleware`: Contient les règles d'accès (`ACCESS_RULES`) par défaut pour différents endpoints API (CORS, Roles, etc.).

## Exemple d'utilisation

```python
from xcore.configurations.core import Xcorecfg
from xcore.configurations.base import Configure

# Initialisation
xcfg = Xcorecfg(conf=Configure())

# Accès aux logs
print(xcfg.custom_config["logs"]["file"])

# Accès aux règles d'accès du middleware
access_rules = xcfg.cfgAcessMidlware()
print(access_rules["ACCESS_RULES"]["/users"])
```

## Détails Techniques

- `custom_config`: Cette propriété contient le dictionnaire de configuration final (fusion entre les valeurs par défaut et celles du fichier JSON).
- `cfgAcessMidlware()`: Retourne spécifiquement la section `midleware` de la configuration.

## Contribution

- Pour modifier les règles d'accès par défaut, modifiez le dictionnaire `default_migration` dans le constructeur de `Xcorecfg`.
- Assurez-vous que les nouvelles entrées de configuration respectent le format `TypedDict` défini dans `deps.py`.
