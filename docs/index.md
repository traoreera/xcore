# xcore – Documentation

> **Framework multi-plugins pour FastAPI** · Python ≥ 3.13 · MIT License

xcore est un framework conçu pour construire des applications FastAPI **modulaires et extensibles** grâce à un système de plugins dynamiques, un scheduler intégré, et une interface d'administration complète.

---

## Démarrage rapide

### 1. Installer le projet

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
git checkout features
poetry install
```

### 2. Lancer le serveur

```bash
uvicorn main:app --reload
```

### 3. Créer votre premier plugin

```
plugins/
└── hello_plugin/
    ├── __init__.py
    ├── run.py
    └── config.yaml
```

```python
# run.py
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
        return {"message": "Hello from xcore!"}
```

Le plugin est automatiquement découvert et monté dans FastAPI au démarrage.

---

## Naviguer dans la documentation

| Section | Description |
|---------|-------------|
| [Architecture](./architecture.md) | Vue d'ensemble technique du framework |
| [Concepts](./concepts/plugins-vs-extensions.md) | Comprendre plugins vs extensions/services |
| [Tutoriels](./tutorials/introduction.md) | Guides pas-à-pas pour créer et utiliser des plugins |
| [Référence](./reference/api-endpoints.md) | API, configuration, anatomie d'un plugin |
| [Contribution](./development/contribution-guide.md) | Contribuer au projet |
| [Glossaire](./glossary.md) | Définitions des termes clés |

---

## Fonctionnalités principales

- **Chargement dynamique de plugins** avec purge du cache Python
- **Hot reload** des plugins et routes FastAPI sans redémarrage
- **Scheduler intégré** pour tâches synchrones et asynchrones
- **Sandbox** : isolation CPU, mémoire et timeout par plugin
- **Administration via API** : liste, reload, monitoring des plugins
- **Authentification JWT** et gestion des rôles intégrées
- **Cache Redis** et journalisation centralisée

---

## Liens utiles

- [Repository GitHub](https://github.com/traoreera/xcore/tree/features)
- [Ouvrir une issue](https://github.com/traoreera/xcore/issues)
- [Pull Requests](https://github.com/traoreera/xcore/pulls)
