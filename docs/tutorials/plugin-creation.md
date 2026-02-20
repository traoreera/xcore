# Créer un plugin complet

Ce tutoriel couvre la création d'un plugin de bout en bout, avec schémas Pydantic, gestion d'erreurs, dépendances et tâche planifiée.

**Prérequis :** avoir suivi l'[introduction](./introduction.md)

---

## Ce que nous allons créer

Un plugin `todo_plugin` qui expose une API CRUD simple pour gérer des tâches (todos), avec validation des données et une tâche de nettoyage automatique.

---

## Structure complète

```
plugins/todo_plugin/
├── __init__.py
├── run.py          ← logique principale
├── router.py       ← expose le router
├── schemas.py      ← modèles Pydantic
├── storage.py      ← stockage en mémoire (remplaçable par DB)
└── config.yaml
```

---

## Étape 1 — Les schémas (`schemas.py`)

```python
# plugins/todo_plugin/schemas.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=3)  # 1=basse, 3=haute

class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: int
    done: bool
    created_at: datetime
```

---

## Étape 2 — Le stockage (`storage.py`)

```python
# plugins/todo_plugin/storage.py
from datetime import datetime
from typing import Dict, List, Optional
from .schemas import TodoCreate, TodoResponse

_store: Dict[int, TodoResponse] = {}
_counter = 0

def create_todo(data: TodoCreate) -> TodoResponse:
    global _counter
    _counter += 1
    todo = TodoResponse(
        id=_counter,
        title=data.title,
        description=data.description,
        priority=data.priority,
        done=False,
        created_at=datetime.utcnow(),
    )
    _store[_counter] = todo
    return todo

def get_all() -> List[TodoResponse]:
    return list(_store.values())

def get_by_id(todo_id: int) -> Optional[TodoResponse]:
    return _store.get(todo_id)

def mark_done(todo_id: int) -> Optional[TodoResponse]:
    if todo_id in _store:
        _store[todo_id].done = True
        return _store[todo_id]
    return None

def delete_done() -> int:
    """Supprime les todos terminés. Retourne le nombre supprimé."""
    to_delete = [k for k, v in _store.items() if v.done]
    for k in to_delete:
        del _store[k]
    return len(to_delete)
```

---

## Étape 3 — Le fichier principal (`run.py`)

```python
# plugins/todo_plugin/run.py
import logging
from fastapi import APIRouter, Request, HTTPException
from .schemas import TodoCreate, TodoResponse
from . import storage

PLUGIN_INFO = {
    "version": "1.0.0",
    "author": "Votre Nom",
    "description": "Gestionnaire de tâches (todos)",
    "Api_prefix": "/app/todo",
    "tag_for_identified": ["todo"],
}

router = APIRouter(prefix="/todo", tags=["todo"])
logger = logging.getLogger("todo_plugin")


class Plugin:
    def __init__(self):
        super(Plugin, self).__init__()
        logger.info("Plugin Todo initialisé.")

    def run(self, request: Request):
        return {"plugin": "todo", "status": "ok"}


# ─── Routes ─────────────────────────────────────────────
@router.get("/", response_model=list[TodoResponse])
def list_todos(request: Request):
    """Liste toutes les tâches."""
    return storage.get_all()


@router.post("/", response_model=TodoResponse, status_code=201)
def create_todo(payload: TodoCreate, request: Request):
    """Crée une nouvelle tâche."""
    todo = storage.create_todo(payload)
    logger.info(f"Todo créé : #{todo.id} '{todo.title}'")
    return todo


@router.get("/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int, request: Request):
    """Récupère une tâche par son ID."""
    todo = storage.get_by_id(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail=f"Todo #{todo_id} introuvable.")
    return todo


@router.patch("/{todo_id}/done", response_model=TodoResponse)
def complete_todo(todo_id: int, request: Request):
    """Marque une tâche comme terminée."""
    todo = storage.mark_done(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail=f"Todo #{todo_id} introuvable.")
    return todo


@router.delete("/cleanup")
def cleanup(request: Request):
    """Supprime toutes les tâches terminées."""
    count = storage.delete_done()
    return {"deleted": count, "message": f"{count} tâche(s) supprimée(s)."}
```

---

## Étape 4 — `__init__.py` et `router.py`

```python
# __init__.py
from .run import Plugin, router
__all__ = ["Plugin", "router"]
```

```python
# router.py
from .run import router
__all__ = ["router"]
```

---

## Étape 5 — `config.yaml`

```yaml
name: todo_plugin
version: "1.0.0"
author: "Votre Nom"
description: "Gestionnaire de tâches todos"
enabled: true
api_prefix: /app/todo
```

---

## Tester le plugin

```bash
# Créer une tâche
curl -X POST http://localhost:8000/app/todo/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Lire la doc xcore", "priority": 2}'

# Lister les tâches
curl http://localhost:8000/app/todo/

# Marquer comme terminée
curl -X PATCH http://localhost:8000/app/todo/1/done

# Nettoyer
curl -X DELETE http://localhost:8000/app/todo/cleanup
```

---

## Points clés à retenir

- **`PLUGIN_INFO`** est obligatoire — sans lui, le `PluginLoader` rejette le plugin.
- **`class Plugin`** doit exister et hériter correctement via `super().__init__()`.
- Les routes sont définies **dans** la classe ou avec les décorateurs `@router.*` au niveau module.
- Utilisez `logging.getLogger("nom_plugin")` pour des logs traçables dans le monitoring.
- Les erreurs doivent lever des `HTTPException` FastAPI pour une réponse HTTP propre.

**Prochaine étape :** [Utiliser un plugin depuis un autre plugin ou service](./plugin-usage.md)
