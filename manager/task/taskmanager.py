from apscheduler.schedulers.background import BackgroundScheduler

# Configuration du logger pour ce module
from ..plManager import logger


class TaskManager:
    """
    Gère les tâches planifiées avec APScheduler
    """

    def __init__(self):
        """Initialise le scheduler"""
        logger.info("📋 Initialisation du TaskManager")

        try:
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()
            logger.info("✅ Scheduler de tâches démarré avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation du scheduler: {e}")
            raise

    def add_job(self, list_jobs=None):
        """
        Ajoute une liste de tâches au scheduler

        :param list_jobs: liste de tâches à ajouter
        """
        if list_jobs is None:
            list_jobs = []

        logger.info(f"📝 Ajout de {len(list_jobs)} tâches au scheduler")

        if not list_jobs:
            logger.warning("⚠️  Aucune tâche à ajouter")
            return

        successful_jobs = 0
        failed_jobs = 0

        try:
            for job in list_jobs:
                try:
                    if job.get("activate", True):
                        response = self._add_job(job)
                        if response is True:
                            successful_jobs += 1
                            logger.info(
                                f"✅ Tâche '{job.get('name', 'unknown')}' ajoutée avec succès"
                            )
                        else:
                            failed_jobs += 1
                            logger.error(
                                f"❌ Échec de l'ajout de la tâche "
                                "'{job.get('name', 'unknown')}': {response}"
                            )
                    else:
                        logger.info(
                            f"⏸️  Tâche '{job.get('name', 'unknown')}' désactivée, ignorée"
                        )

                except Exception as e:
                    failed_jobs += 1
                    logger.error(
                        f"❌ Erreur lors de l'ajout de la tâche '{job.get('name', 'unknown')}': {e}"
                    )

            logger.info(
                f"📊 Résultat de l'ajout des tâches: {successful_jobs} réussies, {failed_jobs} échouées"
            )

        except Exception as e:
            logger.error(f"❌ Erreur générale lors de l'ajout des tâches: {e}")

    def _add_job(self, job: dict):
        """
        Ajoute une tâche au scheduler

        :param job: tâche à ajouter
        """
        job_name = job.get("name", "unknown")
        job_interval = job.get("interval", "unknown")

        logger.debug(
            f"🔧 Configuration de la tâche '{job_name}' avec l'intervalle '{job_interval}'"
        )

        try:
            params: dict = {
                "func": job["func"],
                "trigger": job["interval"],
                "misfire_grace_time": job.get("misfire_grace_time", 30),
                "name": job_name,
                "id": job_name,
            }

            if job["interval"] == "interval":
                minutes = job.get("minutes", 10)
                params["minutes"] = minutes
                logger.debug(
                    f"⏰ Tâche '{job_name}' configurée avec intervalle de {minutes} minutes"
                )

            elif job["interval"] == "cron":
                cron_params = job.get("cron_params", {})
                params.update(cron_params)
                logger.debug(
                    f"⏰ Tâche '{job_name}' configurée avec cron: {cron_params}"
                )

            self.scheduler.add_job(**params)
            logger.info(f"✅ Tâche '{job_name}' ajoutée au scheduler avec succès")
            return True

        except KeyError as e:
            logger.error(f"❌ Paramètre manquant pour la tâche '{job_name}': {e}")
            return f"Missing parameter: {e}"
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'ajout de la tâche '{job_name}': {e}")
            return str(e)

    def reload_jobs(self, list_jobs=None):
        """
        Recharge les tâches avec les nouveaux paramètres

        :param list_jobs: liste de tâches à recharger
        """
        if list_jobs is None:
            list_jobs = []

        logger.info(f"🔄 Rechargement de {len(list_jobs)} tâches")

        try:
            logger.info("🛑 Arrêt du scheduler actuel")
            self.scheduler.shutdown(wait=False)

            logger.info("🔧 Création d'un nouveau scheduler")
            self.scheduler = BackgroundScheduler()

            self.add_job(list_jobs)
            self.scheduler.start()

            logger.info("✅ Tâches rechargées avec succès")

        except Exception as e:
            logger.error(f"❌ Erreur lors du rechargement des tâches: {e}")

    def stop(self):
        """Arrête le scheduler"""
        logger.info("🛑 Arrêt du TaskManager")

        try:
            self.scheduler.shutdown(wait=False)
            logger.info("✅ Scheduler arrêté avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'arrêt du scheduler: {e}")

    def get_jobs_info(self):
        """Récupère des informations sur les tâches actives"""
        try:
            jobs = self.scheduler.get_jobs()
            jobs_info = []

            for job in jobs:
                jobs_info.append(
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run": str(job.next_run_time),
                        "trigger": str(job.trigger),
                    }
                )

            logger.info(f"📊 Informations récupérées pour {len(jobs)} tâches actives")
            return jobs_info

        except Exception as e:
            logger.error(
                f"❌ Erreur lors de la récupération des informations des tâches: {e}"
            )
            return []





    def stopOne(self, job_id):
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"✅ Tâche '{job_id}' arrêtée avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'arrêt de la tâche '{job_id}': {e}")

            
logger.info("📋 Module TaskManager chargé avec succès")
