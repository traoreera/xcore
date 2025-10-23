import threading
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import runtimer
from manager.schemas.taskManager import (
    RestartService,
    TaskListResponse,
    TaskResourcesResponse,
    TaskStatusResponse,
)
from runtimer import backgroundtask, backgroundtask_manager, core_task_threads, crontab

task = APIRouter(prefix="/tasks", tags=["Tasks"])

try:
    import psutil
except ImportError:
    psutil = None

# ────────────────────────────────
#  Récupération des ressources
# ────────────────────────────────


@task.get("/resources", response_model=TaskResourcesResponse)
def resources():
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
def start_task(name: str = Query(..., description="Nom du service à démarrer")):
    """
    Démarre une tâche en arrière-plan si elle n’est pas déjà en cours.
    """
    service = backgroundtask.start_module(name)
    if service:
        backgroundtask_manager.add_service(name=name, target=service)
        return TaskStatusResponse(name=name, status="pending")

    raise HTTPException(status_code=400, detail=f"Service '{name}' déjà en cours.")


# ────────────────────────────────
#  Arrêt d’une tâche
# ────────────────────────────────
@task.post("/stop", response_model=TaskStatusResponse)
def stop_task(name: str = Query(..., description="Nom du service à arrêter")):
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
def get_task_name():
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
def restart_task(name: str = Query(..., description="Nom du service à redémarrer")):
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
def get_meta_data(name: str = Query(..., description="Nom du module à inspecter")):
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
def scheduler():
    """
    Liste les tâches gérées par le planificateur interne (threads actifs).
    """
    return backgroundtask.list_tasks()


# ────────────────────────────────
#  Tâches CRON enregistrées
# ────────────────────────────────
@task.get("/cron")
def cron_jobs():
    """
    Retourne les jobs cron enregistrés dans le crontab manager.
    """
    return crontab.get_jobs_info()


# ────────────────────────────────
#  Tâches core
# ────────────────────────────────


@task.get("/metrics")
def metrics():
    """Retourne les métriques globales du système."""
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory().percent
    threads = threading.active_count()
    return {"cpu_percent": cpu, "memory_percent": mem, "active_threads": threads}


@task.get("/summary")
def summary():
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
def get_config():
    """Retourne la configuration actuelle du manager."""
    return runtimer.cfg.dict() if hasattr(runtimer, "cfg") else {}


@task.post("/config/update")
def update_config(key: str, value: Optional[dict] = None):
    """Modifie dynamiquement la configuration."""
    if hasattr(runtimer, "cfg"):

        runtimer.cfg.conf[key] = value
        runtimer.cfg.save()

        return {"success": True, "updated": {key: value}}
    return {"error": "Aucune configuration chargée"}


@task.post("/reload")
def reload_config():
    """Recharge la configuration globale."""
    try:
        backgroundtask_manager.reload()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@task.post("/config/autorestart")
def update_config(value: bool):
    """Modifie dynamiquement la configuration."""
    if hasattr(runtimer, "cfg"):

        runtimer.cfg.conf["tasks"]["auto_restart"] = value
        runtimer.cfg.save()

        return {"success": True, "updated": {"auto_restart": value}}
    return {"error": "Aucune configuration chargée"}


@task.get("/threads")
def list_threads():
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
