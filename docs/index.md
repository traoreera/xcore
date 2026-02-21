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

## Fonctionnalités principales

- **Chargement dynamique de plugins** avec purge du cache Python
- **Hot reload** des plugins et routes FastAPI sans redémarrage
- **Scheduler intégré** pour tâches synchrones et asynchrones
- **Sandbox** : isolation CPU, mémoire et timeout par plugin
- **Administration via API** : liste, reload, monitoring des plugins
- **Authentification JWT** et gestion des rôles intégrées
- **Cache Redis** et journalisation centralisée

---

```{toctree}
:maxdepth: 1
:caption: 🏠 Vue d'ensemble

architecture
glossary
```

```{toctree}
:maxdepth: 2
:caption: 💡 Concepts

concepts/plugins-vs-extensions
concepts/scheduler-concepts
```

```{toctree}
:maxdepth: 2
:caption: 🎓 Tutoriels

tutorials/introduction
tutorials/plugin-creation
tutorials/plugin-usage
tutorials/service-creation
tutorials/service-usage
```

```{toctree}
:maxdepth: 2
:caption: 📖 Référence

reference/plugin-anatomy
reference/api-endpoints
reference/config-options
reference/commands
```

```{toctree}
:maxdepth: 2
:caption: 🛠️ Développement

development/contribution-guide
development/testing
development/code-style
```

---

## Liens utiles

- [Repository GitHub](https://github.com/traoreera/xcore/tree/features)
- [Ouvrir une issue](https://github.com/traoreera/xcore/issues)
- [Pull Requests](https://github.com/traoreera/xcore/pulls)