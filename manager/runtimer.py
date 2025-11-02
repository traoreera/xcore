from manager.conf import cfg
from manager.crud.taskcurd import ModuleRuntimeManager, core_task_threads
from manager.plManager import logger
from manager.task.corethread import ServiceManager
from manager.task.taskmanager import TaskManager

# Configuration du logger pour ce module

logger.info("⚡ Initialisation du TaskRuntimer")
crontab = TaskManager()


try:
    backgroundtask = ModuleRuntimeManager(
        module_dir=cfg.custom_config["tasks"]["directory"]
    )
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


def on_startup():
    logger.info("Module taskRuntimer importé avec succès")

    # Chargement des modules de tâches en arrière-plan
    loaded_modules = 0
    for module in backgroundtask_modules:
        try:
            if target := (backgroundtask.load_module_target(module.module)):
                backgroundtask_manager.add_service(name=module.module, target=target)
                loaded_modules += 1
                logger.info(f"Module '{module.module}' chargé avec succès")
            else:
                logger.warning(
                    f"Module '{module.module}' n'a pas pu être chargé - target est None"
                )
        except Exception as e:
            logger.error(f"Erreur lors du chargement du module '{module.module}': {e}")
        logger.info(f"{loaded_modules}/{len(backgroundtask_modules)} modules chargés")

    crontab.add_job(core_task_threads)


def on_shutdown():
    logger.info("Module taskRuntimer fermé avec succès")
    backgroundtask_manager.stop_all()
