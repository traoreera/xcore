# Anatomie d'un plugin

Cette page est la référence complète de la structure d'un plugin xcore. Tout plugin doit respecter ce contrat pour être chargé par le `PluginLoader`.

---

## Structure minimale requise

```
mon_plugin/
├── __init__.py     ← obligatoire
├── run.py          ← obligatoire (PLUGIN_INFO + Plugin class + router)
├── router.py       ← recommandé
└── config.yaml     ← recommandé
```

---

## `run.py` — Contrat complet

```python
from fastapi import APIRouter, Request

# ── 1. PLUGIN_INFO ─────────────────────────────────────────────────────────
# Obligatoire. Dictionnaire de métadonnées du plugin.
PLUGIN_INFO = {
    "version": "1.0.0",           # Obligatoire. Versioning SemVer.
    "author": "Nom Auteur",        # Obligatoire.
    "description": "...",          # Recommandé.
    "Api_prefix": "/app/mon_plugin", # Obligatoire. Préfixe de l'API.
    "tag_for_identified": ["mon_plugin"],  # Obligatoire. Tags Swagger.
}

# ── 2. ROUTER ───────────────────────────────────────────────────────────────
# Obligatoire. APIRouter FastAPI qui expose les routes du plugin.
# Le prefix ici est relatif — le préfixe global vient de Api_prefix.
router = APIRouter(prefix="/mon_plugin", tags=["mon_plugin"])

# ── 3. PLUGIN CLASS ─────────────────────────────────────────────────────────
# Obligatoire. Classe principale instanciée par le PluginLoader.
class Plugin:
    def __init__(self):
        super(Plugin, self).__init__()   # Ne pas omettre
        # Initialisation du plugin (logger, connexions, etc.)

    def run(self, request: Request):
        """Point d'entrée optionnel."""
        return {"status": "ok"}

# ── 4. ROUTES ────────────────────────────────────────────────────────────────
# Les routes peuvent être déclarées en dehors ou à l'intérieur de Plugin.
# Convention : @staticmethod + décorateur @router.* au niveau module.

@router.get("/")
@staticmethod
def index(request: Request):
    return {"plugin": "mon_plugin", "status": "running"}
```

---

## `PLUGIN_INFO` — Référence des champs

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `version` | `str` | ✅ | Version SemVer (`"1.0.0"`) |
| `author` | `str` | ✅ | Nom de l'auteur |
| `Api_prefix` | `str` | ✅ | Préfixe global de l'API (ex: `"/app/email"`) |
| `tag_for_identified` | `list[str]` | ✅ | Tags Swagger pour identifier le plugin |
| `description` | `str` | ⬜ | Description courte du plugin |
| `dependencies` | `list[str]` | ⬜ | Packages Python requis |
| `min_xcore_version` | `str` | ⬜ | Version minimale de xcore requise |

---

## `config.yaml` — Référence des champs

```yaml
name: mon_plugin              # Identifiant unique du plugin
version: "1.0.0"              # Doit correspondre à PLUGIN_INFO["version"]
author: "Nom Auteur"
description: "Description courte"
enabled: true                 # false = plugin ignoré au chargement

api_prefix: /app/mon_plugin   # Doit correspondre à PLUGIN_INFO["Api_prefix"]

# Variables d'environnement utilisées par le plugin
env:
  MA_CLE_API: ""
  MON_SECRET: ""

# Dépendances Python supplémentaires
dependencies:
  - "httpx>=0.27"
  - "pydantic[email]"

# Tâches planifiées (optionnel)
tasks:
  - name: "ma_tache"
    interval_seconds: 3600
    enabled: true
```

---

## `__init__.py` — Convention

```python
from .run import Plugin, router
__all__ = ["Plugin", "router"]
```

---

## `router.py` — Convention

```python
from .run import router
__all__ = ["router"]
```

Ce fichier permet au `PluginLoader` d'importer le router indépendamment de la classe `Plugin`.

---

## Règles de validation du PluginLoader

Le `Validator` vérifie qu'un plugin respecte les règles suivantes avant de le charger :

1. Le dossier contient un `__init__.py`
2. Le module `run.py` existe et est importable
3. `PLUGIN_INFO` est un dictionnaire avec tous les champs obligatoires
4. La classe `Plugin` existe et est instanciable
5. `router` est une instance de `fastapi.APIRouter`
6. `PLUGIN_INFO["Api_prefix"]` commence par `"/app/"`
7. Pas de conflit de préfixe avec un plugin déjà chargé

Si une règle n'est pas respectée, le plugin est rejeté avec un message d'erreur détaillé dans les logs.

---

## Exemple complet minimal

```python
# plugins/ping_plugin/run.py
from fastapi import APIRouter, Request

PLUGIN_INFO = {
    "version": "0.1.0",
    "author": "xcore",
    "Api_prefix": "/app/ping",
    "tag_for_identified": ["ping"],
}

router = APIRouter(prefix="/ping", tags=["ping"])

class Plugin:
    def __init__(self):
        super(Plugin, self).__init__()

    @router.get("/")
    @staticmethod
    def ping(request: Request):
        return {"pong": True}
```

```python
# plugins/ping_plugin/__init__.py
from .run import Plugin, router
__all__ = ["Plugin", "router"]
```
