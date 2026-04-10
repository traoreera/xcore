# Exemple : Plugin Complet (Complete Plugin CRUD)

Cet exemple complet présente l'implémentation d'un plugin gérant des tâches (Todos) avec intégration de services, routes HTTP et validation de données.

---

## 1. Structure du Répertoire

```text
todo_plugin/
├── plugin.yaml
└── src/
    └── main.py
```

---

## 2. Le Manifeste (`plugin.yaml`)

```yaml
name: todo_plugin
version: 1.0.0
author: XCore Team
description: Plugin CRUD Todo intégrant services, routes et validation
execution_mode: trusted
entry_point: src/main.py

# Dépendances sur les services SQL et Cache
requires:
  - database_service
  - cache_service

# Permissions requises
permissions:
  - resource: "db.todos"
    actions: ["read", "write", "delete"]
    effect: allow
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
```

---

## 3. Le Code Source (`src/main.py`)

```python
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base
from xcore.sdk import (
    TrustedBase,
    AutoDispatchMixin,
    RoutedPlugin,
    BaseAsyncRepository,
    action,
    route,
    validate_payload,
    ok,
    error
)

# 1. Modèle SQLAlchemy pour la base de données
Base = declarative_base()

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    completed = Column(Boolean, default=False)

# 2. Modèles Pydantic pour la validation
class CreateTodo(BaseModel):
    title: str

class UpdateTodo(BaseModel):
    title: str | None = None
    completed: bool | None = None

# 3. Repository pour l'accès aux données
class TodoRepository(BaseAsyncRepository[Todo]):
    pass

# 4. Classe Plugin principale
class Plugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    """
    Plugin Todo complet utilisant le SDK XCore.
    """

    async def on_load(self) -> None:
        """Initialisation des services."""
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.repo = TodoRepository(Todo)

        # Créer les tables si elles n'existent pas (en développement uniquement)
        if self.ctx.env == "development":
             async with self.db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    # --- Actions IPC (Inter-Process Communication) ---

    @action("create")
    @validate_payload(CreateTodo)
    async def create_todo_ipc(self, data: dict) -> dict:
        """Crée une nouvelle tâche via IPC."""
        async with self.db.session() as session:
            todo = Todo(title=data["title"])
            await self.repo.create(session, todo)
            await session.commit()

            # Invalide le cache de la liste des todos
            await self.cache.delete("todo:list")

            return ok(id=todo.id, title=todo.title)

    # --- Routes HTTP REST (Exposées sur /plugin/todo_plugin/...) ---

    @route("/", method="GET")
    async def list_todos(self):
        """Liste toutes les tâches (avec cache)."""
        # Tentative de récupération depuis le cache
        cached = await self.cache.get("todo:list")
        if cached:
            return {"todos": cached, "cached": True}

        # Sinon, récupération en DB
        async with self.db.session() as session:
            todos = await self.repo.get_all(session)
            results = [{"id": t.id, "title": t.title, "completed": t.completed} for t in todos]

            # Mise en cache pour 60 secondes
            await self.cache.set("todo:list", results, ttl=60)

            return {"todos": results, "cached": False}

    @route("/{todo_id}", method="GET")
    async def get_todo(self, todo_id: int):
        """Récupère une tâche par son ID."""
        async with self.db.session() as session:
            todo = await self.repo.get_by_id(session, todo_id)
            if not todo:
                return error("Tâche non trouvée", status_code=404)
            return {"id": todo.id, "title": todo.title, "completed": todo.completed}

    @route("/{todo_id}", method="DELETE", status_code=204)
    async def delete_todo(self, todo_id: int):
        """Supprime une tâche."""
        async with self.db.session() as session:
            await self.repo.delete(session, todo_id)
            await session.commit()
            await self.cache.delete("todo:list")
            return None
```

---

## 4. Test de l'Exemple

### Création d'une tâche via IPC

```bash
curl -X POST http://localhost:8082/plugin/ipc/todo_plugin/create \
  -H "X-Plugin-Key: change-me-in-production" \
  -d '{"payload": {"title": "Apprendre XCore"}}'

# Réponse :
# {"status":"ok","plugin":"todo_plugin","action":"create","result":{"status":"ok","id":1,"title":"Apprendre XCore"}}
```

### Lecture des tâches via HTTP REST

```bash
curl http://localhost:8082/plugin/todo_plugin/

# Réponse :
# {"todos":[{"id":1,"title":"Apprendre XCore","completed":false}],"cached":false}
```

---

## Points Clés de l'Exemple

✅ **Persistence** : Utilisation du service DB avec le pattern Repository.
✅ **Caching** : Utilisation du service Cache pour optimiser les requêtes `list`.
✅ **Validation** : Décorateur `@validate_payload` avec modèles Pydantic.
✅ **Routage** : Décorateur `@route` pour construire une API REST standard.
✅ **Cycle de vie** : Initialisation et nettoyage gérés dans `on_load`.
