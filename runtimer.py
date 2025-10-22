from rich import print_json

from manager.crud.taskcurd import ModuleRuntimeManager, core_task_threads
from manager.plManager import logger
from manager.conf import cfg
from manager.task.corethread import ServiceManager
from manager.task.taskmanager import TaskManager

# Configuration du logger pour ce module

logger.info("⚡ Initialisation du TaskRuntimer")
crontab = TaskManager()


try:
    backgroundtask = ModuleRuntimeManager(module_dir=cfg.get("tasks", "directory"))
    logger.info("📋 ModuleRuntimeManager initialisé avec succès")
except Exception as e:
    logger.error(f"Une exception s'est produite lors de l'initialisation du ModuleRuntimeManager")
    logger.exception(e)
    raise

try:
    backgroundtask_modules = backgroundtask.get_enabled_modules()
    module_count = len(backgroundtask_modules) if backgroundtask_modules else 0
    logger.info(f"📦 {module_count} modules de tâches en arrière-plan chargés")
except Exception as e:
    logger.error(f"❌ Erreur lors du chargement des modules: {e}")
    backgroundtask_modules = []

try:
    backgroundtask_manager = ServiceManager()
    logger.info("🔧 ServiceManager de tâches en arrière-plan initialisé")
except Exception as e:
    logger.error(f"❌ Erreur lors de l'initialisation du ServiceManager: {e}")
    raise


def main_loop(service):
    """Boucle principale de monitoring des tâches"""
    logger.info("🔄 Démarrage de la boucle principale de monitoring")

    iteration_count = 0

    try:
        while service.running:
            iteration_count += 1
            logger.debug(f"🔄 Itération #{iteration_count} de la boucle de monitoring")

            tasks = {}
            try:
                if tasklist := backgroundtask_manager.list_services():
                    logger.debug(f"📊 Monitoring de {len(tasklist)} services")

                    for task in tasklist:
                        try:
                            usage = backgroundtask_manager.get_service_resource_usage(
                                task["service"]
                            )
                            tasks[task["name"]] = usage

                            # Log des alertes de performance
                            if isinstance(usage, dict) and "cpu_time" in usage:
                                # Plus de 10 secondes de CPU
                                if usage["cpu_time"] > 10 and task["name"] != "plugins":
                                    logger.warning(
                                        f"⚠️  Service '{task['name']}' utilise beaucoup de CPU: {usage['cpu_time']}s"
                                    )

                            if usage.get("memory_mb", 0) > 300:  # Plus de 100MB
                                logger.warning(
                                    f"⚠️  Service '{task['name']}' utilise beaucoup de mémoire: {usage['memory_mb']}MB"
                                )

                        except Exception as e:
                            logger.error(
                                f"❌ Erreur lors du monitoring du service '{task.get('name', 'unknown')}': {e}"
                            )
                            tasks[task.get("name", "unknown")] = {"error": str(e)}

                    # Affichage périodique des stats (toutes les 10 itérations)
                    if iteration_count % 10 == 0:
                        logger.info(
                            f"📊 Stats des services (itération #{iteration_count}):"
                        )
                        print_json(data=tasks)

                else:
                    if iteration_count == 1:  # Log seulement au début
                        logger.warning("⚠️  Aucun service trouvé pour le monitoring")

            except Exception as e:
                logger.error(
                    f"❌ Erreur lors du monitoring des tâches (itération #{iteration_count}): {e}"
                )

            # Petite pause pour éviter la surcharge
            import time

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("⌨️  Interruption clavier détectée, arrêt des services")
        try:
            backgroundtask_manager.stop_all()
            logger.info("✅ Tous les services arrêtés suite à l'interruption")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'arrêt des services: {e}")
    except Exception as e:
        logger.error(f"❌ Erreur dans la boucle principale de monitoring: {e}")
        raise




logger.info("⚡ Module TaskRuntimer chargé avec succès")
