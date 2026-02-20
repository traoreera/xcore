# Introduction à xcore

Ce tutoriel vous guide de l'installation jusqu'à votre première API fonctionnelle avec un plugin custom.

**Durée estimée :** 15 minutes  
**Prérequis :** Python ≥ 3.13, connaissances de base de FastAPI

---

## Ce que vous allez construire

À la fin de ce tutoriel, vous aurez :
- xcore installé et fonctionnel
- Un plugin `hello_plugin` créé et monté automatiquement
- Une route `GET /app/hello/` qui répond en JSON
- Une compréhension du cycle de vie d'un plugin

---

## Étape 1 — Installer xcore

Clonez le repository et installez les dépendances avec Poetry :

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
git checkout features
poetry install
```

Vérifiez que l'installation fonctionne :

```bash
poetry run python -c "import fastapi; print('FastAPI OK')"
```

---

## Étape 2 — Lancer le serveur

```bash
uvicorn main:app --reload
```

Visitez `http://localhost:8000/docs` — vous verrez l'interface Swagger avec les routes du core (admin, auth, manager).

---

## Étape 3 — Créer votre premier plugin

Créez la structure suivante dans le dossier `plugins/` :

```bash
mkdir plugins/hello_plugin
touch plugins/hello_plugin/__init__.py
touch plugins/hello_plugin/run.py
touch plugins/hello_plugin/config.yaml
```

### `run.py`

```python
from fastapi import APIRouter, Request

PLUGIN_INFO = {
    "version": "1.0.0",
    "author": "Votre Nom",
    "Api_prefix": "/app/hello",
    "tag_for_identified": ["hello"],
}

router = APIRouter(prefix="/hello", tags=["hello"])

class Plugin:
    def __init__(self):
        super(Plugin, self).__init__()

    @router.get("/")
    @staticmethod
    def run(request: Request):
        return {"message": "Hello from xcore!", "plugin": "hello_plugin"}
```

### `__init__.py`

```python
from .run import Plugin, router
__all__ = ["Plugin", "router"]
```

### `config.yaml`

```yaml
name: hello_plugin
version: "1.0.0"
author: "Votre Nom"
enabled: true
api_prefix: /app/hello
```

---

## Étape 4 — Vérifier le chargement

Comme le serveur tourne avec `--reload`, sauvegardez vos fichiers et observez les logs :

```
INFO:     Plugin 'hello_plugin' chargé avec succès.
INFO:     Route montée : GET /app/hello/
```

Testez votre plugin :

```bash
curl http://localhost:8000/app/hello/
# {"message": "Hello from xcore!", "plugin": "hello_plugin"}
```

Et dans Swagger à `http://localhost:8000/docs`, une nouvelle section `hello` est apparue.

---

## Étape 5 — Ajouter une route avec paramètre

Ajoutez une nouvelle route dans `run.py` :

```python
@router.get("/{name}")
@staticmethod
def greet(name: str, request: Request):
    return {"message": f"Bonjour, {name}!"}
```

Sauvegardez — le hot reload recharge automatiquement le plugin. Testez :

```bash
curl http://localhost:8000/app/hello/monde
# {"message": "Bonjour, monde!"}
```

---

## Résumé

Vous avez appris à :
- Installer et lancer xcore
- Créer un plugin avec la structure minimale requise
- Exposer des routes FastAPI via un plugin
- Profiter du hot reload pour développer sans redémarrage

**Prochaine étape :** [Créer un plugin complet](./plugin-creation.md) avec schémas Pydantic, gestion d'erreurs et tâches planifiées.
