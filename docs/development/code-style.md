# Style de code

xcore suit les conventions Python modernes. Ce guide définit les règles à respecter pour toute contribution.

---

## Outils utilisés

| Outil | Rôle | Commande |
|-------|------|----------|
| `black` | Formatage automatique | `make format` |
| `ruff` | Linting (remplace flake8, isort) | `make lint` |
| `mypy` | Vérification des types | `make typecheck` |

---

## Formatage (`black`)

Le formatage est entièrement délégué à `black`. Ne perdez pas de temps à débattre du style — `make format` applique les règles automatiquement.

```bash
make format
# ou
poetry run black .
```

Quelques règles clés appliquées par black :
- Longueur de ligne maximale : **88 caractères**
- Guillemets doubles `"` pour les chaînes
- Virgule finale dans les listes/dicts multilignes

---

## Linting (`ruff`)

```bash
make lint
# ou
poetry run ruff check .
```

Règles importantes vérifiées par ruff :
- Imports non utilisés
- Variables non utilisées
- Ordre des imports (stdlib → third-party → local)
- Shadowing de builtins Python

---

## Typage

xcore utilise les annotations de types Python. Elles sont **obligatoires** pour toutes les fonctions publiques.

```python
# ✅ Bien
def creer_plugin(nom: str, version: str) -> dict[str, str]:
    return {"nom": nom, "version": version}

# ❌ Mal
def creer_plugin(nom, version):
    return {"nom": nom, "version": version}
```

Pour les types complexes, utilisez `typing` ou la syntaxe Python 3.10+ :

```python
from typing import Optional, List   # Python 3.9 et avant
# ou
def ma_fonction(items: list[str] | None = None) -> dict[str, int]:  # Python 3.10+
    ...
```

---

## Conventions de nommage

| Élément | Convention | Exemple |
|---------|-----------|---------|
| Variables | `snake_case` | `plugin_info` |
| Fonctions | `snake_case` | `charger_plugin()` |
| Classes | `PascalCase` | `PluginLoader` |
| Constantes | `SCREAMING_SNAKE_CASE` | `PLUGIN_INFO` |
| Fichiers | `snake_case` | `plugin_loader.py` |
| Dossiers | `snake_case` | `email_plugin/` |
| Routes FastAPI | `kebab-case` | `/mon-endpoint/` |

---

## Structure des fichiers

### Ordre des imports

```python
# 1. Stdlib
import os
import logging
from datetime import datetime
from typing import Optional

# 2. Third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

# 3. Local (extensions, plugins)
from extensions.services.database import get_db
from extensions.services.auth import get_current_user
from .schemas import MonSchema
```

### Ordre dans un fichier de plugin

```python
# 1. Imports
# 2. PLUGIN_INFO
# 3. router = APIRouter(...)
# 4. logger = logging.getLogger(...)
# 5. Schémas Pydantic locaux (ou importés depuis schemas.py)
# 6. Fonctions utilitaires / dépendances
# 7. Routes (@router.get, @router.post, ...)
# 8. class Plugin
```

---

## Docstrings

Les fonctions publiques doivent avoir une docstring courte. Les docstrings apparaissent dans l'interface Swagger pour les routes FastAPI.

```python
@router.post("/envoyer", response_model=EmailResponse)
async def envoyer_email(payload: EmailPayload):
    """
    Envoie un email en arrière-plan.
    
    - **to** : liste des destinataires
    - **subject** : sujet de l'email  
    - **body** : corps en texte brut
    - **html** : corps HTML optionnel
    """
    ...
```

---

## Gestion des erreurs

Utilisez toujours `HTTPException` de FastAPI pour les erreurs dans les routes. Évitez de laisser remonter des exceptions Python brutes.

```python
# ✅ Bien
from fastapi import HTTPException

def get_item(item_id: int):
    item = db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item #{item_id} introuvable.")
    return item

# ❌ Mal
def get_item(item_id: int):
    return db[item_id]  # KeyError si absent → réponse 500 non informative
```

---

## Logging

Utilisez le module `logging` standard. Chaque plugin doit avoir son propre logger nommé.

```python
import logging

logger = logging.getLogger("nom_du_plugin")

# Niveaux à utiliser
logger.debug("Détail de débogage")
logger.info("Action normale")
logger.warning("Situation inattendue mais non bloquante")
logger.error("Erreur récupérable")
logger.exception("Erreur avec traceback complet")  # dans un except
```

N'utilisez **jamais** `print()` pour les logs — les `print()` ne sont pas capturés par le système de monitoring de xcore.
