# Trusted Plugin Example (Advanced)

Un exemple complet de plugin **Trusted** avec architecture modulaire utilisant `router.py` séparé et configuration via `.env`.

## Cas d'usage : Gestionnaire de Tâches (Task Manager)

Ce plugin gère des tâches avec persistance, notifications, et statistiques avancées.

## Structure du Plugin

```
plugins/task_manager/
├── plugin.yaml           # Manifest du plugin
├── .env                  # Configuration locale (non commitée)
├── src/
│   ├── __init__.py
│   ├── main.py          # Point d'entrée principal
│   ├── router.py        # Routes HTTP FastAPI séparées
│   ├── models.py        # Modèles de données
│   └── services.py      # Logique métier
└── data/
    └── .gitkeep         # Dossier pour persistence
```

## 1. plugin.yaml

```yaml
name: task_manager
version: 2.0.0
author: XCore Team
description: |
  Gestionnaire de tâches avancé avec:
  - CRUD complet via HTTP et IPC
  - Notifications par email
  - Statistiques et rapports
  - Persistance dans la base de données

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

# Dépendances inter-plugins
requires:
  - users_plugin  # Nécessite le plugin users pour les assignations

# Permissions détaillées
permissions:
  - resource: "db.*"
    actions: ["read", "write", "delete"]
    effect: allow
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "ext.email*"
    actions: ["send"]
    effect: allow
  - resource: "scheduler"
    actions: ["schedule", "cancel"]
    effect: allow
  - resource: "audit.log"
    actions: ["write"]
    effect: allow

# Variables d'environnement injectées
env:
  TASKS_TABLE: "tasks"
  DEFAULT_PRIORITY: "medium"
  MAX_TASKS_PER_USER: "100"

# Configuration du .env
envconfiguration:
  inject: true
  required: true

# Ressources allouées
resources:
  timeout_seconds: 30
  max_memory_mb: 256
  max_disk_mb: 100
  rate_limit:
    calls: 1000
    period_seconds: 60

# Runtime
runtime:
  health_check:
    enabled: true
    interval_seconds: 30
    timeout_seconds: 5
  retry:
    max_attempts: 3
    backoff_seconds: 1.0

# Filesystem
filesystem:
  allowed_paths: ["data/", "exports/"]
  denied_paths: ["src/config/"]

# Configuration personnalisée du plugin
notifications:
  email_template: "task_notification"
  enabled: true

priorities:
  levels: ["low", "medium", "high", "urgent"]
  default_days:
    low: 7
    medium: 3
    high: 1
    urgent: 0
```

## 2. .env (Configuration locale)

```bash
# Database Configuration
TASK_MANAGER_DB_URL=postgresql://localhost/taskmanager
TASK_MANAGER_DB_POOL_SIZE=10

# Notification Settings
TASK_MANAGER_SMTP_HOST=smtp.company.com
TASK_MANAGER_SMTP_PORT=587
TASK_MANAGER_SMTP_USER=notifications@company.com
TASK_MANAGER_SMTP_PASS=secure_password_here
TASK_MANAGER_NOTIFY_ON_ASSIGN=true
TASK_MANAGER_NOTIFY_ON_COMPLETE=true

# Feature Flags
TASK_MANAGER_ENABLE_ANALYTICS=true
TASK_MANAGER_ENABLE_EXPORTS=true
TASK_MANAGER_EXPORT_FORMATS=json,csv,pdf

# Security
TASK_MANAGER_ENCRYPTION_KEY=${TASK_MANAGER_SECRET_KEY}
TASK_MANAGER_MAX_EXPORT_SIZE_MB=50
```

## 3. src/models.py

```python
"""Modèles de données pour Task Manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Statuts possibles d'une tâche."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Niveaux de priorité."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    """Représentation d'une tâche."""
    id: int | None = None
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_by: int = 0
    assigned_to: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    due_date: datetime | None = None
    completed_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convertit la tâche en dictionnaire."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Crée une tâche depuis un dictionnaire."""
        return cls(
            id=data.get("id"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            priority=TaskPriority(data.get("priority", "medium")),
            created_by=data.get("created_by", 0),
            assigned_to=data.get("assigned_to"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskFilter:
    """Filtres pour la recherche de tâches."""
    status: list[TaskStatus] | None = None
    priority: list[TaskPriority] | None = None
    assigned_to: int | None = None
    created_by: int | None = None
    tags: list[str] | None = None
    due_before: datetime | None = None
    due_after: datetime | None = None
    search_query: str | None = None

    def to_sql_conditions(self) -> tuple[str, list]:
        """Génère les conditions SQL pour le filtrage."""
        conditions = []
        params = []

        if self.status:
            conditions.append(f"status IN ({','.join(['%s'] * len(self.status))})")
            params.extend([s.value for s in self.status])

        if self.priority:
            conditions.append(f"priority IN ({','.join(['%s'] * len(self.priority))})")
            params.extend([p.value for p in self.priority])

        if self.assigned_to is not None:
            conditions.append("assigned_to = %s")
            params.append(self.assigned_to)

        if self.created_by is not None:
            conditions.append("created_by = %s")
            params.append(self.created_by)

        if self.tags:
            conditions.append("tags @> %s::jsonb")
            params.append(self.tags)

        if self.due_before:
            conditions.append("due_date <= %s")
            params.append(self.due_before)

        if self.due_after:
            conditions.append("due_date >= %s")
            params.append(self.due_after)

        if self.search_query:
            conditions.append("(title ILIKE %s OR description ILIKE %s)")
            search = f"%{self.search_query}%"
            params.extend([search, search])

        return " AND ".join(conditions) if conditions else "1=1", params
```

## 4. src/services.py

```python
"""Services métier pour Task Manager."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from xcore.sdk import ok, error

from .models import Task, TaskFilter, TaskStatus, TaskPriority


class TaskService:
    """Service de gestion des tâches."""

    def __init__(self, ctx, config: dict) -> None:
        self.ctx = ctx
        self.config = config
        self.db = ctx.services.get("db")
        self.cache = ctx.services.get("cache")
        self.email = ctx.services.get("ext.email")
        self.scheduler = ctx.services.get("scheduler")
        self.audit = ctx.services.get("audit.log")
        self.table = config.get("TASKS_TABLE", "tasks")
        self.max_per_user = int(config.get("MAX_TASKS_PER_USER", 100))

    async def create_task(self, task_data: dict, created_by: int) -> dict:
        """Crée une nouvelle tâche."""
        try:
            # Vérifier la limite de tâches par utilisateur
            count = await self._count_user_tasks(created_by)
            if count >= self.max_per_user:
                return error(
                    f"Limite de {self.max_per_user} tâches atteinte",
                    code="limit_reached"
                )

            # Créer la tâche
            task = Task(
                title=task_data["title"],
                description=task_data.get("description", ""),
                priority=TaskPriority(task_data.get("priority", "medium")),
                created_by=created_by,
                assigned_to=task_data.get("assigned_to"),
                tags=task_data.get("tags", []),
                metadata=task_data.get("metadata", {}),
            )

            # Calculer la date d'échéance si non fournie
            if not task.due_date:
                days = self.config.get("priorities", {}).get("default_days", {}).get(
                    task.priority.value, 3
                )
                task.due_date = datetime.utcnow() + timedelta(days=days)

            # Persister en base
            task.id = await self._insert_task(task)

            # Logger l'action
            await self._audit_log("task_created", task.id, created_by)

            # Notifier si assigné
            if task.assigned_to and self.config.get("notifications", {}).get("enabled"):
                await self._notify_assignment(task)

            # Planifier un rappel si urgent
            if task.priority == TaskPriority.URGENT:
                await self._schedule_reminder(task)

            # Invalider le cache
            await self._invalidate_cache(f"user:{created_by}:tasks")

            return ok(task=task.to_dict())

        except Exception as e:
            return error(f"Erreur création tâche: {str(e)}", code="create_failed")

    async def update_task(self, task_id: int, updates: dict, updated_by: int) -> dict:
        """Met à jour une tâche existante."""
        try:
            task = await self._get_task_by_id(task_id)
            if not task:
                return error("Tâche non trouvée", code="not_found")

            # Mettre à jour les champs
            if "title" in updates:
                task.title = updates["title"]
            if "description" in updates:
                task.description = updates["description"]
            if "status" in updates:
                old_status = task.status
                task.status = TaskStatus(updates["status"])
                if task.status == TaskStatus.COMPLETED and old_status != TaskStatus.COMPLETED:
                    task.completed_at = datetime.utcnow()
                    await self._notify_completion(task)
            if "priority" in updates:
                task.priority = TaskPriority(updates["priority"])
            if "assigned_to" in updates:
                task.assigned_to = updates["assigned_to"]
                await self._notify_assignment(task)
            if "tags" in updates:
                task.tags = updates["tags"]
            if "metadata" in updates:
                task.metadata.update(updates["metadata"])

            task.updated_at = datetime.utcnow()

            # Persister
            await self._update_task_in_db(task)

            # Audit
            await self._audit_log("task_updated", task_id, updated_by, updates)

            # Invalider le cache
            await self._invalidate_cache(f"task:{task_id}")

            return ok(task=task.to_dict())

        except Exception as e:
            return error(f"Erreur mise à jour: {str(e)}", code="update_failed")

    async def get_task(self, task_id: int) -> dict:
        """Récupère une tâche par ID."""
        try:
            # Vérifier le cache d'abord
            cache_key = f"task:{task_id}"
            cached = await self.cache.get(cache_key)
            if cached:
                return ok(task=cached)

            task = await self._get_task_by_id(task_id)
            if not task:
                return error("Tâche non trouvée", code="not_found")

            # Mettre en cache
            await self.cache.set(cache_key, task.to_dict(), ttl=300)

            return ok(task=task.to_dict())

        except Exception as e:
            return error(f"Erreur récupération: {str(e)}", code="fetch_failed")

    async def list_tasks(self, filters: TaskFilter, page: int = 1, page_size: int = 20) -> dict:
        """Liste les tâches avec filtrage et pagination."""
        try:
            offset = (page - 1) * page_size
            condition, params = filters.to_sql_conditions()

            # Requête avec pagination
            sql = f"""
                SELECT * FROM {self.table}
                WHERE {condition}
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        ELSE 4
                    END,
                    due_date ASC NULLS LAST
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])

            rows = await self.db.fetch(sql, *params)
            tasks = [Task.from_dict(dict(row)).to_dict() for row in rows]

            # Comptage total pour pagination
            count_sql = f"SELECT COUNT(*) FROM {self.table} WHERE {condition}"
            total = await self.db.fetchval(count_sql, *params[:-2])

            return ok(
                tasks=tasks,
                pagination={
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "pages": (total + page_size - 1) // page_size
                }
            )

        except Exception as e:
            return error(f"Erreur liste: {str(e)}", code="list_failed")

    async def delete_task(self, task_id: int, deleted_by: int) -> dict:
        """Supprime une tâche."""
        try:
            task = await self._get_task_by_id(task_id)
            if not task:
                return error("Tâche non trouvée", code="not_found")

            await self.db.execute(f"DELETE FROM {self.table} WHERE id = %s", task_id)

            await self._audit_log("task_deleted", task_id, deleted_by)
            await self._invalidate_cache(f"task:{task_id}")

            return ok(deleted=True)

        except Exception as e:
            return error(f"Erreur suppression: {str(e)}", code="delete_failed")

    async def get_statistics(self, user_id: int | None = None) -> dict:
        """Récupère les statistiques des tâches."""
        try:
            where_clause = "WHERE created_by = %s" if user_id else ""
            params = [user_id] if user_id else []

            sql = f"""
                SELECT
                    status,
                    priority,
                    COUNT(*) as count
                FROM {self.table}
                {where_clause}
                GROUP BY status, priority
            """

            rows = await self.db.fetch(sql, *params)

            stats = {
                "by_status": {},
                "by_priority": {},
                "total": 0
            }

            for row in rows:
                status = row["status"]
                priority = row["priority"]
                count = row["count"]

                stats["by_status"][status] = stats["by_status"].get(status, 0) + count
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + count
                stats["total"] += count

            # Tâches en retard
            overdue_sql = f"""
                SELECT COUNT(*) FROM {self.table}
                WHERE due_date < NOW() AND status NOT IN ('completed', 'cancelled')
            """
            if user_id:
                overdue_sql += " AND created_by = %s"

            stats["overdue"] = await self.db.fetchval(overdue_sql, *params)

            return ok(statistics=stats)

        except Exception as e:
            return error(f"Erreur statistiques: {str(e)}", code="stats_failed")

    # Méthodes privées

    async def _count_user_tasks(self, user_id: int) -> int:
        """Compte les tâches d'un utilisateur."""
        sql = f"SELECT COUNT(*) FROM {self.table} WHERE created_by = %s"
        return await self.db.fetchval(sql, user_id)

    async def _get_task_by_id(self, task_id: int) -> Task | None:
        """Récupère une tâche par ID."""
        sql = f"SELECT * FROM {self.table} WHERE id = %s"
        row = await self.db.fetchrow(sql, task_id)
        return Task.from_dict(dict(row)) if row else None

    async def _insert_task(self, task: Task) -> int:
        """Insère une nouvelle tâche."""
        sql = f"""
            INSERT INTO {self.table}
            (title, description, status, priority, created_by, assigned_to,
             created_at, updated_at, due_date, tags, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING id
        """
        return await self.db.fetchval(
            sql,
            task.title, task.description, task.status.value, task.priority.value,
            task.created_by, task.assigned_to, task.created_at, task.updated_at,
            task.due_date, json.dumps(task.tags), json.dumps(task.metadata)
        )

    async def _update_task_in_db(self, task: Task) -> None:
        """Met à jour une tâche en base."""
        sql = f"""
            UPDATE {self.table} SET
                title = %s, description = %s, status = %s, priority = %s,
                assigned_to = %s, updated_at = %s, due_date = %s,
                completed_at = %s, tags = %s::jsonb, metadata = %s::jsonb
            WHERE id = %s
        """
        await self.db.execute(
            sql,
            task.title, task.description, task.status.value, task.priority.value,
            task.assigned_to, task.updated_at, task.due_date,
            task.completed_at, json.dumps(task.tags), json.dumps(task.metadata),
            task.id
        )

    async def _notify_assignment(self, task: Task) -> None:
        """Envoie une notification d'assignation."""
        if not task.assigned_to or not self.email:
            return

        await self.email.send(
            to_user_id=task.assigned_to,
            subject=f"Nouvelle tâche assignée: {task.title}",
            template="task_assigned",
            data={"task": task.to_dict()}
        )

    async def _notify_completion(self, task: Task) -> None:
        """Notifie le créateur de la complétion."""
        if not self.email:
            return

        await self.email.send(
            to_user_id=task.created_by,
            subject=f"Tâche complétée: {task.title}",
            template="task_completed",
            data={"task": task.to_dict()}
        )

    async def _schedule_reminder(self, task: Task) -> None:
        """Planifie un rappel pour une tâche urgente."""
        if not self.scheduler:
            return

        await self.scheduler.schedule(
            plugin="task_manager",
            action="send_reminder",
            payload={"task_id": task.id},
            run_at=task.due_date - timedelta(hours=1)
        )

    async def _audit_log(self, action: str, task_id: int, user_id: int, details: dict | None = None) -> None:
        """Log une action d'audit."""
        if self.audit:
            await self.audit.write(
                action=action,
                resource=f"task:{task_id}",
                user_id=user_id,
                details=details
            )

    async def _invalidate_cache(self, pattern: str) -> None:
        """Invalide les entrées de cache."""
        if self.cache:
            await self.cache.delete_pattern(pattern)
```

## 5. src/router.py

```python
"""Routes HTTP FastAPI pour Task Manager.

Ce fichier sépare la logique de routage HTTP de la logique métier IPC,
permettant une meilleure organisation du code et une maintenance facilitée.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Path, Body

from .models import TaskStatus, TaskPriority, TaskFilter


def create_router(plugin_instance) -> APIRouter:
    """
    Crée et configure le router FastAPI.

    Args:
        plugin_instance: Instance du plugin pour accéder aux services
    """
    router = APIRouter(
        prefix="/tasks",
        tags=["tasks"],
    )
    service = plugin_instance.task_service

    @router.get("/", response_model=dict)
    async def list_tasks(
        status: list[TaskStatus] = Query(None, description="Filtrer par statuts"),
        priority: list[TaskPriority] = Query(None, description="Filtrer par priorités"),
        assigned_to: int = Query(None, description="Filtrer par assigné"),
        search: str = Query(None, description="Recherche textuelle"),
        page: int = Query(1, ge=1, description="Numéro de page"),
        page_size: int = Query(20, ge=1, le=100, description="Taille de page"),
    ):
        """
        Liste les tâches avec filtrage et pagination.

        Exemple: /tasks/?status=pending&priority=high,urgent&page=1
        """
        filters = TaskFilter(
            status=status,
            priority=priority,
            assigned_to=assigned_to,
            search_query=search,
        )
        result = await service.list_tasks(filters, page, page_size)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.post("/", response_model=dict, status_code=201)
    async def create_task(
        title: str = Body(..., min_length=1, max_length=200),
        description: str = Body("", max_length=5000),
        priority: TaskPriority = Body(TaskPriority.MEDIUM),
        assigned_to: int | None = Body(None),
        tags: list[str] = Body([]),
        due_date: datetime | None = Body(None),
        metadata: dict[str, Any] = Body({}),
    ):
        """
        Crée une nouvelle tâche.

        Le créateur est déduit du contexte d'authentification.
        """
        # Récupérer l'ID utilisateur du contexte (exemple)
        current_user_id = plugin_instance.ctx.get("user_id", 0)

        task_data = {
            "title": title,
            "description": description,
            "priority": priority.value,
            "assigned_to": assigned_to,
            "tags": tags,
            "due_date": due_date.isoformat() if due_date else None,
            "metadata": metadata,
        }

        result = await service.create_task(task_data, current_user_id)

        if result.get("status") == "error":
            if result.get("code") == "limit_reached":
                raise HTTPException(status_code=429, detail=result.get("msg"))
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.get("/{task_id}", response_model=dict)
    async def get_task(
        task_id: int = Path(..., ge=1, description="ID de la tâche"),
    ):
        """Récupère une tâche par son ID."""
        result = await service.get_task(task_id)

        if result.get("status") == "error":
            if result.get("code") == "not_found":
                raise HTTPException(status_code=404, detail="Tâche non trouvée")
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.patch("/{task_id}", response_model=dict)
    async def update_task(
        task_id: int = Path(..., ge=1),
        updates: dict = Body(...),
    ):
        """
        Met à jour partiellement une tâche.

        Seuls les champs fournis sont mis à jour.
        """
        current_user_id = plugin_instance.ctx.get("user_id", 0)

        result = await service.update_task(task_id, updates, current_user_id)

        if result.get("status") == "error":
            if result.get("code") == "not_found":
                raise HTTPException(status_code=404, detail="Tâche non trouvée")
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.delete("/{task_id}", response_model=dict)
    async def delete_task(
        task_id: int = Path(..., ge=1),
    ):
        """Supprime une tâche."""
        current_user_id = plugin_instance.ctx.get("user_id", 0)

        result = await service.delete_task(task_id, current_user_id)

        if result.get("status") == "error":
            if result.get("code") == "not_found":
                raise HTTPException(status_code=404, detail="Tâche non trouvée")
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.post("/{task_id}/complete", response_model=dict)
    async def complete_task(
        task_id: int = Path(..., ge=1),
    ):
        """Marque une tâche comme complétée."""
        current_user_id = plugin_instance.ctx.get("user_id", 0)

        result = await service.update_task(
            task_id,
            {"status": "completed"},
            current_user_id
        )

        if result.get("status") == "error":
            if result.get("code") == "not_found":
                raise HTTPException(status_code=404, detail="Tâche non trouvée")
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.get("/statistics/dashboard", response_model=dict)
    async def get_statistics():
        """Récupère les statistiques globales pour le dashboard."""
        result = await service.get_statistics()

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.get("/my/stats", response_model=dict)
    async def get_my_statistics():
        """Récupère les statistiques de l'utilisateur courant."""
        current_user_id = plugin_instance.ctx.get("user_id", 0)

        result = await service.get_statistics(current_user_id)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    @router.get("/overdue", response_model=dict)
    async def get_overdue_tasks(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        """Liste les tâches en retard."""
        filters = TaskFilter(
            status=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            due_before=datetime.utcnow(),
        )
        result = await service.list_tasks(filters, page, page_size)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("msg"))
        return result

    return router
```

## 6. src/main.py

```python
"""Point d'entrée du plugin Task Manager."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from xcore.sdk import TrustedBase, ok, error, action, require_service

from .models import TaskFilter, TaskStatus
from .services import TaskService
from .router import create_router


class Plugin(TrustedBase):
    """
    Plugin Task Manager - Version Trusted.

    Caractéristiques:
    - Accès complet aux services (db, cache, email, scheduler)
    - Routes HTTP séparées dans router.py
    - Configuration via .env
    - Persistence en base de données
    - Notifications et audit
    """

    def __init__(self) -> None:
        super().__init__()
        self.task_service: TaskService | None = None
        self.config: dict[str, Any] = {}

    async def on_load(self) -> None:
        """Initialisation du plugin."""
        print("📋 Task Manager - Chargement...")

        # Charger la configuration depuis l'environnement
        self._load_config()

        # Initialiser le service métier
        self.task_service = TaskService(self.ctx, self.config)

        print(f"✅ Task Manager v2.0.0 chargé")
        print(f"   Table: {self.config.get('TASKS_TABLE', 'tasks')}")
        print(f"   Max tasks/user: {self.config.get('MAX_TASKS_PER_USER', 100)}")
        print(f"   Notifications: {self.config.get('notifications', {}).get('enabled', False)}")

    async def on_unload(self) -> None:
        """Nettoyage à l'arrêt."""
        print("👋 Task Manager - Arrêt")

    def _load_config(self) -> None:
        """Charge la configuration depuis les variables d'environnement."""
        # Config depuis plugin.yaml (déjà parsée dans ctx.config)
        yaml_config = self.ctx.config if self.ctx else {}

        # Config depuis .env (injectée dans ctx.env)
        env_config = self.ctx.env if self.ctx else {}

        # Fusionner les configs
        self.config = {
            # Valeurs du .env
            "TASKS_TABLE": env_config.get("TASKS_TABLE", "tasks"),
            "DEFAULT_PRIORITY": env_config.get("DEFAULT_PRIORITY", "medium"),
            "MAX_TASKS_PER_USER": env_config.get("MAX_TASKS_PER_USER", "100"),

            # Valeurs complexes depuis plugin.yaml
            "notifications": yaml_config.get("notifications", {"enabled": True}),
            "priorities": yaml_config.get("priorities", {
                "levels": ["low", "medium", "high", "urgent"],
                "default_days": {"low": 7, "medium": 3, "high": 1, "urgent": 0}
            }),

            # Toutes les variables d'environnement pour référence
            **env_config,
        }

    def get_router(self) -> APIRouter | None:
        """
        Fournit le router FastAPI.

        Les routes sont définies dans router.py pour une meilleure organisation.
        """
        if not self.task_service:
            return None
        return create_router(self)

    # ========== Actions IPC ==========

    async def handle(self, action: str, payload: dict) -> dict:
        """Dispatch les actions IPC."""
        if not self.task_service:
            return error("Plugin non initialisé", code="not_ready")

        # Mapping des actions
        handlers = {
            "create_task": self._handle_create,
            "update_task": self._handle_update,
            "get_task": self._handle_get,
            "list_tasks": self._handle_list,
            "delete_task": self._handle_delete,
            "complete_task": self._handle_complete,
            "get_statistics": self._handle_stats,
            "bulk_update": self._handle_bulk_update,
            "send_reminder": self._handle_reminder,
        }

        handler = handlers.get(action)
        if not handler:
            return error(f"Action inconnue: {action}", code="unknown_action")

        try:
            return await handler(payload)
        except Exception as e:
            return error(f"Erreur: {str(e)}", code="internal_error")

    async def _handle_create(self, payload: dict) -> dict:
        """Crée une tâche via IPC."""
        user_id = payload.get("user_id", 0)
        task_data = payload.get("task", {})
        return await self.task_service.create_task(task_data, user_id)

    async def _handle_update(self, payload: dict) -> dict:
        """Met à jour une tâche via IPC."""
        task_id = payload.get("task_id")
        updates = payload.get("updates", {})
        user_id = payload.get("user_id", 0)

        if not task_id:
            return error("task_id requis", code="missing_param")

        return await self.task_service.update_task(task_id, updates, user_id)

    async def _handle_get(self, payload: dict) -> dict:
        """Récupère une tâche via IPC."""
        task_id = payload.get("task_id")

        if not task_id:
            return error("task_id requis", code="missing_param")

        return await self.task_service.get_task(task_id)

    async def _handle_list(self, payload: dict) -> dict:
        """Liste les tâches via IPC."""
        filters = TaskFilter(
            status=[TaskStatus(s) for s in payload.get("status", [])] if payload.get("status") else None,
            priority=payload.get("priority"),
            assigned_to=payload.get("assigned_to"),
            created_by=payload.get("created_by"),
            tags=payload.get("tags"),
        )
        page = payload.get("page", 1)
        page_size = payload.get("page_size", 20)

        return await self.task_service.list_tasks(filters, page, page_size)

    async def _handle_delete(self, payload: dict) -> dict:
        """Supprime une tâche via IPC."""
        task_id = payload.get("task_id")
        user_id = payload.get("user_id", 0)

        if not task_id:
            return error("task_id requis", code="missing_param")

        return await self.task_service.delete_task(task_id, user_id)

    async def _handle_complete(self, payload: dict) -> dict:
        """Marque une tâche comme complétée via IPC."""
        task_id = payload.get("task_id")
        user_id = payload.get("user_id", 0)

        if not task_id:
            return error("task_id requis", code="missing_param")

        return await self.task_service.update_task(
            task_id, {"status": "completed"}, user_id
        )

    async def _handle_stats(self, payload: dict) -> dict:
        """Récupère les statistiques via IPC."""
        user_id = payload.get("user_id")
        return await self.task_service.get_statistics(user_id)

    async def _handle_bulk_update(self, payload: dict) -> dict:
        """Met à jour plusieurs tâches en lot."""
        task_ids = payload.get("task_ids", [])
        updates = payload.get("updates", {})
        user_id = payload.get("user_id", 0)

        results = []
        for task_id in task_ids:
            result = await self.task_service.update_task(task_id, updates, user_id)
            results.append({"task_id": task_id, "result": result})

        return ok(updated=len(results), results=results)

    async def _handle_reminder(self, payload: dict) -> dict:
        """Envoie un rappel pour une tâche."""
        task_id = payload.get("task_id")
        if not task_id:
            return error("task_id requis", code="missing_param")

        result = await self.task_service.get_task(task_id)
        if result.get("status") != "ok":
            return result

        task = result.get("task", {})

        # Envoyer le rappel par email
        if self.ctx.services.get("ext.email"):
            await self.ctx.services["ext.email"].send(
                to_user_id=task.get("assigned_to"),
                subject=f"Rappel: Tâche urgente - {task.get('title')}",
                template="task_reminder",
                data={"task": task}
            )

        return ok(reminder_sent=True)
```

## Utilisation

### Endpoints HTTP

```bash
# Lister toutes les tâches
curl "http://localhost:8082/plugins/task_manager/tasks/"

# Créer une tâche
curl -X POST "http://localhost:8082/plugins/task_manager/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Implémenter l\'authentification",
    "description": "Ajouter OAuth2 au système",
    "priority": "high",
    "assigned_to": 42,
    "tags": ["auth", "security"]
  }'

# Récupérer une tâche
curl "http://localhost:8082/plugins/task_manager/tasks/123"

# Mettre à jour une tâche
curl -X PATCH "http://localhost:8082/plugins/task_manager/tasks/123" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "priority": "urgent"
  }'

# Marquer comme complétée
curl -X POST "http://localhost:8082/plugins/task_manager/tasks/123/complete"

# Supprimer une tâche
curl -X DELETE "http://localhost:8082/plugins/task_manager/tasks/123"

# Filtrer les tâches
curl "http://localhost:8082/plugins/task_manager/tasks/?status=pending&priority=high,urgent"

# Tâches en retard
curl "http://localhost:8082/plugins/task_manager/tasks/overdue"

# Statistiques globales
curl "http://localhost:8082/plugins/task_manager/tasks/statistics/dashboard"

# Mes statistiques
curl "http://localhost:8082/plugins/task_manager/tasks/my/stats"
```

### Appels IPC

```bash
# Créer une tâche
curl -X POST http://localhost:8082/app/task_manager/create_task \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 42,
    "task": {
      "title": "Review PR #123",
      "priority": "high",
      "assigned_to": 43
    }
  }'

# Lister avec filtres
curl -X POST http://localhost:8082/app/task_manager/list_tasks \
  -H "Content-Type: application/json" \
  -d '{
    "status": ["pending", "in_progress"],
    "priority": ["high", "urgent"],
    "page": 1,
    "page_size": 50
  }'

# Mise à jour en lot
curl -X POST http://localhost:8082/app/task_manager/bulk_update \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 42,
    "task_ids": [1, 2, 3],
    "updates": {"priority": "low"}
  }'

# Statistiques
curl -X POST http://localhost:8082/app/task_manager/get_statistics \
  -H "Content-Type: application/json" \
  -d '{"user_id": 42}'
```

## Points Clés de l'Architecture

### 1. Séparation des Responsabilités

```
main.py      -> Point d'entrée, dispatch IPC, cycle de vie
router.py    -> Routes HTTP, validation des entrées
services.py  -> Logique métier, accès aux données
models.py    -> Structures de données, validation
```

### 2. Configuration via .env

- Variables sensibles (SMTP, DB) dans `.env` (non commité)
- Configuration structurelle dans `plugin.yaml`
- Fusion au chargement dans `on_load()`

### 3. Plugin Trusted - Accès Illimités

- **DB**: Lecture/écriture/suppression
- **Cache**: Patterns avec invalidation
- **Email**: Notifications automatiques
- **Scheduler**: Rappels programmés
- **Audit**: Traçabilité complète

### 4. Patterns Utilisés

- **Service Layer**: Séparation métier/transport
- **Repository Pattern**: Abstraction DB
- **DTO**: Modèles pour transfert de données
- **Cache Aside**: Lecture/écriture avec cache
- **Audit Trail**: Log de toutes les actions

## Tests

```python
# tests/test_task_manager.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_create_task():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8082/plugins/task_manager/tasks/",
            json={
                "title": "Test Task",
                "description": "A test task",
                "priority": "medium"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "ok"
        assert data["task"]["title"] == "Test Task"

@pytest.mark.asyncio
async def test_list_tasks_with_filters():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8082/plugins/task_manager/tasks/",
            params={
                "status": "pending",
                "priority": ["high", "urgent"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "pagination" in data
```
