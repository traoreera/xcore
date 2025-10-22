import time
from fastapi import FastAPI

from manager import cfg
import runtimer as taskRuntimer
from manager import AppType, Manager
from manager.plManager import logger
from manager.routes.task import task
from data.routes.users import usersRoutes,authRouters

app = FastAPI(title="Core API with Plugin System", version="1.0.0")


app.include_router(task)
app.include_router(usersRoutes)
app.include_router(authRouters)


manager = Manager(
    app=app,
    entry_point=cfg.get("plugins", "entry_point"),
    plugins_dir=cfg.get("plugins", "directory"),
    interval=cfg.get("plugins", "interval"),
    app_type=AppType.FASTAPI,base_routes=app.routes
)


manager.snapshot.ignore_ext = cfg.get('snapshot','extensions')
manager.snapshot.ignore_file = cfg.get('snapshot','filenames')
manager.snapshot.ignore_hidden = cfg.get('snapshot','hidden')



@app.on_event("startup")
async def startup_event():

    manager.run_plugins()
    try:

        logger.info("📦 Module taskRuntimer importé avec succès")

        # Chargement des modules de tâches en arrière-plan
        loaded_modules = 0
        for module in taskRuntimer.backgroundtask_modules:
            try:
                if target := (
                    taskRuntimer.backgroundtask.load_module_target(module.module)
                ):
                    taskRuntimer.backgroundtask_manager.add_service(
                        name=module.module, target=target
                    )
                    loaded_modules += 1
                    logger.info(f"✅ Module '{module.module}' chargé avec succès")
                else:
                    logger.warning(
                        f"⚠️  Module '{module.module}' n'a pas pu être chargé - target est None"
                    )
            except Exception as e:
                logger.error(
                    f"❌ Erreur lors du chargement du module '{module.module}': {e}"
                )

        logger.info(
            f"📊 {loaded_modules}/{len(taskRuntimer.backgroundtask_modules)} modules chargés"
        )

        # Ajout du service principal
        try:
            taskRuntimer.backgroundtask_manager.add_service(
                name="taskRuntimer Thread Instance Indentication",
                target=taskRuntimer.main_loop,
            )

            #taskRuntimer.backgroundtask_manager.add_service("wath plugins folder", target=service_main)

            logger.info("🔄 Service principal taskRuntimer ajouté")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'ajout du service principal: {e}")

    except Exception as e:
        logger.critical(f"🚨 Erreur critique lors du démarrage: {e}")
        raise

    taskRuntimer.crontab.add_job(taskRuntimer.core_task_threads)


@app.on_event("shutdown")
async def shutdown_event():
    manager.stop_watching()
    logger.info("📦 Arrêt des services de tâches en arrière-plan...")

    taskRuntimer.backgroundtask_manager.stop_all()
    logger.info("✅ Tous les services de tâches arrêtés")

    manager.close_db()
    logger.info("🗃️  Connexion à la base de données fermée")

    logger.info("🎯 Arrêt du runtime terminé avec succès")
