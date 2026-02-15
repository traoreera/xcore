from integrations.conf import cfg
from integrations.crud.taskcurd import ModuleRuntimeManager, core_task_threads
from integrations.plManager import logger
from integrations.task.corethread import ServiceManager
from integrations.task.taskmanager import TaskManager
from integrations.tools.error import Error


# Configuration du logger pour ce module

logger.info("⚡ Initialisation du TaskRuntimer")
crontab = TaskManager()



backgroundtask = ModuleRuntimeManager(module_dir=cfg.custom_config["tasks"]["directory"])
logger.info("🔧 ModuleRuntimeManager de tâches en arrière-plan initialisé")

backgroundtask_modules = backgroundtask.get_enabled_modules()
module_count = len(backgroundtask_modules) if backgroundtask_modules else 0
logger.info(f"{module_count} modules de tâches en arrière-plan chargés")


backgroundtask_manager = ServiceManager()
logger.info("🔧 ServiceManager de tâches en arrière-plan initialisé")





@Error.exception_handler
def on_startup():
    for mod in backgroundtask_modules:
        backgroundtask_manager.add_service(name=mod.module, target=backgroundtask.load_module_target(mod.module))

    crontab.add_job(core_task_threads)


@Error.exception_handler
def on_shutdown():
    logger.info("Module taskRuntimer fermé avec succès")
    backgroundtask_manager.stop_all()
