import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

import manager.runtimer as runtimer
from admin import dependencies
from manager.runtimer import (
    backgroundtask,
    backgroundtask_manager,
    core_task_threads,
    crontab,
)
from manager.schemas.taskManager import (
    RestartService,
    TaskListResponse,
    TaskResourcesResponse,
    TaskStatusResponse,
)

task = APIRouter(prefix="/system", tags=["system"])

try:
    import psutil
except ImportError:
    psutil = None

# ────────────────────────────────
#  Récupération des ressources
# ────────────────────────────────


@task.get(
    "/resources",
    response_model=TaskResourcesResponse,
)
def resources(user=Depends(dependencies.require_admin)):
    """
    Retourne la consommation de ressources (CPU, RAM, durée, etc.) pour chaque service actif.
    """
    task_list = {}

    for task_data in backgroundtask_manager.list_services():
        name = task_data["name"]
        usage = backgroundtask_manager.get_service_resource_usage(task_data["service"])
        task_list[name] = usage

    return TaskResourcesResponse(root=task_list)


# ────────────────────────────────
#  Démarrage d’une tâche
# ────────────────────────────────
@task.post("/start", response_model=TaskStatusResponse)
def start_task(
    name: str = Query(..., description="Nom du service à démarrer"),
    user=Depends(dependencies.require_superuser),
):
    """
    Démarre une tâche en arrière-plan si elle n’est pas déjà en cours.
    """
    if service := backgroundtask.start_module(name):
        backgroundtask_manager.add_service(name=name, target=service)
        return TaskStatusResponse(name=name, status="pending")

    raise HTTPException(status_code=400, detail=f"Service '{name}' déjà en cours.")


# ────────────────────────────────
#  Arrêt d’une tâche
# ────────────────────────────────
@task.post("/stop", response_model=TaskStatusResponse)
def stop_task(
    name: str = Query(..., description="Nom du service à arrêter"),
    user=Depends(dependencies.require_superuser),
):
    """
    Arrête un service en cours d’exécution.
    """
    if backgroundtask_manager.remove_service(name):
        return TaskStatusResponse(name=name, status="stopped")

    raise HTTPException(status_code=404, detail=f"Service '{name}' introuvable.")


# ────────────────────────────────
#  Liste des tâches actives
# ────────────────────────────────
@task.get("/list", response_model=TaskListResponse)
def get_task_name(user=Depends(dependencies.require_admin)):
    """
    Retourne la liste des tâches avec leur statut.
    """
    tasks = backgroundtask_manager.list_services()
    formatted = [{"name": t["name"], "status": t["status"]} for t in tasks]
    return TaskListResponse(tasks=formatted)


# ────────────────────────────────
#  Redémarrage d’un service
# ────────────────────────────────
@task.post("/restart", response_model=RestartService)
def restart_task(
    name: str = Query(..., description="Nom du service à redémarrer"),
    user=Depends(dependencies.require_superuser),
):
    """
    Redémarre un service en utilisant backgroundtask_manager.
    """
    if backgroundtask_manager.restart(name):
        return RestartService(success=True, status="pending", name=name)
    return RestartService(success=False, status="failed", name=name)


# ────────────────────────────────
#  Métadonnées d’un module
# ────────────────────────────────
@task.get("/meta")
def get_meta_data(
    name: str = Query(..., description="Nom du module à inspecter"),
    user=Depends(dependencies.require_admin),
):
    """
    Extrait et retourne les métadonnées d’un module (ex: version, docstring, etc.)
    """
    try:
        return backgroundtask.extract_metadata(name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────
#  Liste des tâches planifiées
# ────────────────────────────────
@task.get("/scheduler")
def scheduler(request: Request, user=Depends(dependencies.require_admin)):
    """
    Liste les tâches gérées par le planificateur interne (threads actifs).
    """
    request.client.host

    return backgroundtask.list_tasks()


# ────────────────────────────────
#  Tâches CRON enregistrées
# ────────────────────────────────
@task.get("/cron")
def cron_jobs(request: Request, user=Depends(dependencies.require_admin)):
    """
    Retourne les jobs cron enregistrés dans le crontab manager.
    """
    return crontab.get_jobs_info()


# ────────────────────────────────
#  Tâches core
# ────────────────────────────────


@task.get("/metrics")
def metrics(request: Request, user=Depends(dependencies.require_admin)):
    """Retourne les métriques globales du système."""
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory().percent
    threads = threading.active_count()
    return {"cpu_percent": cpu, "memory_percent": mem, "active_threads": threads}


@task.get("/summary")
def summary(request: Request, user=Depends(dependencies.require_admin)):
    """Donne une vue synthétique de tous les services."""
    result = []
    for name, svc in backgroundtask_manager.services.items():
        status = "running" if svc.running else "stopped"
        uptime = round(time.time() - svc.start_time, 2) if svc.start_time else 0
        result.append({"name": name, "status": status, "uptime": uptime})
    return {"summary": result}


# ────────────────────────────────
#  Configuration du manager
# ────────────────────────────────


@task.get("/config")
def get_config(request: Request, user=Depends(dependencies.require_admin)):
    """Retourne la configuration actuelle du manager."""
    return runtimer.cfg.dict() if hasattr(runtimer, "cfg") else {}


@task.post("/config/update")
def update_config(
    request: Request,
    key: str,
    value: Optional[dict] = None,
    user=Depends(dependencies.require_superuser),
):
    """Modifie dynamiquement la configuration."""
    if hasattr(runtimer, "cfg"):

        runtimer.cfg.conf[key] = value
        runtimer.cfg.save()

        return {"success": True, "updated": {key: value}}
    return {"error": "Aucune configuration chargée"}


@task.post("/reload")
def reload_config(request: Request, user=Depends(dependencies.require_superuser)):
    """Recharge la configuration globale."""
    try:
        backgroundtask_manager.reload()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@task.post("/config/autorestart")
def update_config(value: bool, user=Depends(dependencies.require_superuser)):
    """Modifie dynamiquement la configuration."""
    if hasattr(runtimer, "cfg"):

        runtimer.cfg.conf["tasks"]["auto_restart"] = value
        runtimer.cfg.save()

        return {"success": True, "updated": {"auto_restart": value}}
    return {"error": "Aucune configuration chargée"}


@task.get("/threads")
def list_threads(user=Depends(dependencies.require_admin)):
    """Liste les threads actifs."""
    return [
        {
            "id": t.ident,
            "name": t.name,
            "alive": t.is_alive(),
            "daemon": t.daemon,
            "native": t.native_id,
        }
        for t in threading.enumerate()
    ]
