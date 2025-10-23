from manager.conf import cfg
from manager.crud.taskcurd import ModuleRuntimeManager, core_task_threads
from manager.plManager import logger
from manager.task.corethread import ServiceManager
from manager.task.taskmanager import TaskManager

# Configuration du logger pour ce module

logger.info("⚡ Initialisation du TaskRuntimer")
crontab = TaskManager()


try:
    backgroundtask = ModuleRuntimeManager(module_dir=cfg.get("tasks", "directory"))
    logger.info("ModuleRuntimeManager initialisé avec succès")
except Exception as e:
    logger.error(
        f"Une exception s'est produite lors de l'initialisation du ModuleRuntimeManager"
    )
    logger.exception(e)
    raise

try:
    backgroundtask_modules = backgroundtask.get_enabled_modules()
    module_count = len(backgroundtask_modules) if backgroundtask_modules else 0
    logger.info(f"{module_count} modules de tâches en arrière-plan chargés")
except Exception as e:
    logger.error(f"Erreur lors du chargement des modules: {e}")
    backgroundtask_modules = []

try:
    backgroundtask_manager = ServiceManager()
    logger.info("🔧 ServiceManager de tâches en arrière-plan initialisé")
except Exception as e:
    logger.error(f"Erreur lors de l'initialisation du ServiceManager: {e}")
    raise


logger.info("⚡ Module TaskRuntimer chargé avec succès")
