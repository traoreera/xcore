from fastapi import FastAPI
from ma import AppType, Manager
from ma import runtimer as taskRuntimer
from ma.plManager import logg
from ma.plManager.snapshot import SnapshotIgnorer

er

app = FastAPI(title="Core API with Plugin System", version="1.0.0")


manager = Manager(
    app=app,
    entry_point="run",
    plugins_dir="plugins",
    interval=2,
    app_type=AppType.FASTAPI,
    base_routes=app.routes,
)


manager.snapshot.ignore_ext = SnapshotIgnorer.exclude_extensions
manager.snapshot.ignore_file = SnapshotIgnorer.exclude_filenames
manager.snapshot.ignore_hidden = SnapshotIgnorer.exclude_hidden


@app.on_event("startup")
async def startup_event():

    manager.run_plugins()
    manager.start_watching()
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
