# Guide de Démarrage Rapide

Ce guide vous montre comment démarrer rapidement avec xcore et créer votre premier plugin.

## Démarrage en 5 Minutes

### 1. Lancer le Serveur

```bash
# Activer l'environnement Poetry
poetry shell

# Lancer le serveur de développement
uvicorn main:app --reload
```

Le serveur est maintenant accessible sur `http://localhost:8000`.

### 2. Explorer l'API

Ouvrez votre navigateur et accédez à :

- **Swagger UI**: http://localhost:8000/docs
- **Documentation interactive** avec test des endpoints

### 3. Authentification

#### Créer un compte utilisateur

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "full_name": "John Doe"
  }'
```

#### Se connecter

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=SecurePass123!"
```

Réponse :
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

#### Utiliser le Token

```bash
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

## Votre Premier Plugin

Créons un plugin simple qui expose une API de gestion de tâches.

### Étape 1: Structure du Plugin

```bash
mkdir -p plugins/todo_plugin
```

### Étape 2: Configuration du Plugin

Créez `plugins/todo_plugin/plugin.json` :

```json
{
  "name": "todo_plugin",
  "version": "1.0.0",
  "author": "Votre Nom",
  "description": "Un plugin de gestion de tâches simple",
  "active": true,
  "async": true,
  "api_prefix": "/todo",
  "tags": ["todo", "tasks"],
  "dependencies": []
}
```

### Étape 3: Créer le Point d'Entrée

Créez `plugins/todo_plugin/__init__.py` :

```python
"""Plugin de gestion de tâches pour xcore."""

from .run import router, PLUGIN_INFO

__all__ = ["router", "PLUGIN_INFO"]
```

### Étape 4: Développer les Routes

Créez `plugins/todo_plugin/run.py` :

```python
"""Routes du plugin Todo."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Import de l'authentification xcore
from auth.routes import get_current_user
from auth.models import User

PLUGIN_INFO = {
    "name": "todo_plugin",
    "version": "1.0.0",
    "author": "Votre Nom",
    "description": "Gestion de tâches",
    "api_prefix": "/todo",
    "tags": ["todo"],
}

router = APIRouter(prefix="/todo", tags=["todo"])

# Stockage en mémoire (remplacer par une base de données en production)
tasks_db = []
task_id_counter = 1


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"  # low, medium, high


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: str
    completed: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_id: int

    class Config:
        from_attributes = True


@router.get("/", response_model=List[Task])
async def list_tasks(
    completed: Optional[bool] = None,
    current_user: User = Depends(get_current_user)
):
    """Lister toutes les tâches de l'utilisateur."""
    user_tasks = [t for t in tasks_db if t["user_id"] == current_user.id]

    if completed is not None:
        user_tasks = [t for t in user_tasks if t["completed"] == completed]

    return user_tasks


@router.post("/", response_model=Task, status_code=201)
async def create_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_user)
):
    """Créer une nouvelle tâche."""
    global task_id_counter

    new_task = {
        "id": task_id_counter,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "completed": False,
        "created_at": datetime.now(),
        "updated_at": None,
        "user_id": current_user.id
    }

    tasks_db.append(new_task)
    task_id_counter += 1

    return new_task


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user)
):
    """Récupérer une tâche spécifique."""
    task = next(
        (t for t in tasks_db if t["id"] == task_id and t["user_id"] == current_user.id),
        None
    )

    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    return task


@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour une tâche."""
    task = next(
        (t for t in tasks_db if t["id"] == task_id and t["user_id"] == current_user.id),
        None
    )

    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    update_data = task_update.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now()

    task.update(update_data)

    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user)
):
    """Supprimer une tâche."""
    global tasks_db

    task_index = next(
        (i for i, t in enumerate(tasks_db)
         if t["id"] == task_id and t["user_id"] == current_user.id),
        None
    )

    if task_index is None:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    tasks_db.pop(task_index)

    return None


@router.post("/{task_id}/complete", response_model=Task)
async def complete_task(
    task_id: int,
    current_user: User = Depends(get_current_user)
):
    """Marquer une tâche comme terminée."""
    task = next(
        (t for t in tasks_db if t["id"] == task_id and t["user_id"] == current_user.id),
        None
    )

    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    task["completed"] = True
    task["updated_at"] = datetime.now()

    return task
```

### Étape 5: Recharger le Plugin

Le plugin est automatiquement détecté et chargé par xcore. Consultez les logs pour vérifier :

```bash
# Les logs afficheront quelque chose comme :
# [INFO] Plugin chargé: todo_plugin v1.0.0
# [INFO] Routes ajoutées: /todo/*
```

### Étape 6: Tester le Plugin

```bash
# Créer une tâche
curl -X POST http://localhost:8000/todo/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Apprendre xcore",
    "description": "Lire la documentation complète",
    "priority": "high"
  }'

# Lister les tâches
curl http://localhost:8000/todo/ \
  -H "Authorization: Bearer $TOKEN"

# Marquer comme terminée
curl -X POST http://localhost:8000/todo/1/complete \
  -H "Authorization: Bearer $TOKEN"
```

## Utilisation des Hooks

Les hooks permettent d'interagir avec le cycle de vie de l'application.

### Exemple: Hook après création de tâche

Modifiez `plugins/todo_plugin/run.py` :

```python
from hooks.hooks import hooks

# Hook appelé après création d'une tâche
@hooks.on("todo.task.created")
async def on_task_created(event):
    task = event.data
    print(f"Nouvelle tâche créée: {task['title']}")
    # Envoyer une notification, logger, etc.

# Dans la fonction create_task, ajoutez :
await hooks.emit("todo.task.created", {"task": new_task})
```

## Utilisation du Cache

Ajoutez du caching pour améliorer les performances :

```python
from cache.decorators import cached

@router.get("/")
@cached(ttl=300)  # Cache pendant 5 minutes
async def list_tasks(...):
    # Cette fonction sera mise en cache
    ...
```

## Prochaines Étapes

- [Tutoriel Complet Plugin](tutorials/create-plugin.md) - Plugin avancé avec base de données
- [Frontend](frontend.md) - Créer des interfaces utilisateur
- [Authentification](auth.md) - Sécuriser vos plugins
- [Admin](admin.md) - Gérer les rôles et permissions

## Ressources Utiles

- **Code Exemples**: Voir le dossier `examples/`
- **Tests**: Exécuter `pytest tests/`
- **Documentation API**: http://localhost:8000/docs
