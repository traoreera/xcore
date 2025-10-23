import os
import threading
import time
from typing import Any

from manager.conf import cfg
from manager.plManager import logger
from manager.schemas.taskManager import TaskResource
from manager.tools.error import Error, ExceptionResponse

try:
    import psutil
except ImportError:
    psutil = None  # psutil est facultatif mais recommandé


class ThreadedService:
    """Gestion d’un service exécuté dans un thread séparé."""

    def __init__(self, target, name="ThreadedService"):
        self.target = target
        self.name = name
        self.running = False
        self.thread = None
        self.thread_id = None
        self.start_time = None

    def _run(self):
        """Exécution interne du thread."""
        self.running = True
        self.start_time = time.time()
        self.thread_id = threading.get_native_id()

        logger.info(f"[{self.name}] → Démarrage du service (TID: {self.thread_id})")
        try:
            self.target(self)
        except Exception as e:
            logger.exception(f"[{self.name}] ✖ Exception capturée : {e}")
        finally:
            self.running = False
            logger.warning(
                f"[{self.name}] ← Service terminé (durée: {round(time.time() - self.start_time, 2)}s)"
            )

    def start(self):
        """Lance le service dans un nouveau thread."""
        if self.running:
            logger.info(f"[{self.name}] ⚠ Déjà en cours d’exécution")
            return

        self.thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self.thread.start()
        logger.debug(f"[{self.name}] Thread lancé avec succès")

    def stop(self, callback=None):
        """Stoppe le service proprement."""
        if not self.running:
            logger.warning(f"[{self.name}] ⚠ Service déjà arrêté")
            return

        logger.info(f"[{self.name}] ⏹ Arrêt demandé")
        self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                logger.warning(f"[{self.name}] ⚠ Thread non terminé proprement")

        if callback:
            try:
                logger.info(f"[{self.name}] ☑ Exécution du callback d’arrêt…")
                callback()
            except Exception as e:
                logger.error(f"[{self.name}] ⚠ Erreur dans le callback : {e}")

        logger.info(f"[{self.name}] ✅ Service arrêté")

    def restart(self, callback=None):
        """Redémarre le service."""
        logger.info(f"[{self.name}] 🔁 Redémarrage du service…")
        self.stop(callback=callback)
        time.sleep(0.5)
        self.start()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class ServiceManager:
    """Orchestrateur des services multithread."""

    def __init__(self):
        self.services = {}
        self.restart_attempts = {}
        if cfg.get("tasks", "auto_restart"):
            self.add_service("auto_restart", self.auto_restart)

    def add_service(self, name, target):
        """Ajoute et démarre un nouveau service."""
        if name in self.services:
            logger.warning(f"⚠ Le service '{name}' existe déjà")
            return

        service = ThreadedService(target=target, name=name)
        self.services[name] = service
        service.start()
        logger.info(f"[ServiceManager]  Service '{name}' ajouté et lancé")

    def remove_service(self, name):
        """Supprime un service et l’arrête proprement."""
        service = self.services.get(name)
        if not service:
            logger.warning(f"⚠ Le service '{name}' n'existe pas")
            return False

        service.stop()
        del self.services[name]
        logger.info(f"[ServiceManager] 🗑 Service '{name}' supprimé")
        return True

    def list_services(self):
        taks = []
        for name, service in self.services.items():
            status = "running" if service.running else "stopped"
            taks.append({"name": name, "service": service, "status": status})
        return taks

    def stop_all(self):
        """Arrête tous les services actifs."""
        logger.info("[ServiceManager] ⏹ Arrêt de tous les services")
        for service in list(self.services.values()):
            service.stop()

    def stop_service(self, name):
        """Arrête un service spécifique."""
        service = self.services.get(name)
        if service:
            service.stop()
            logger.info(f"[ServiceManager] Service '{name}' arrêté")
            return True
        else:
            logger.warning(f"[ServiceManager] ⚠ Service '{name}' introuvable")
            return False

    def restart(self, name):
        """Redémarre un service spécifique."""
        service = self.services.get(name)
        if not service:
            logger.warning(f"[ServiceManager] ⚠ Service '{name}' introuvable")
            return False

        service.restart()
        logger.info(f"[ServiceManager] Service '{name}' redémarré")
        return True

    def get_service_resource_usage(self, service) -> TaskResource | ExceptionResponse:
        """Retourne les statistiques de ressources du thread lié au service."""
        if not psutil:
            logger.warning("[ServiceManager] psutil non disponible")
            return {"error": "psutil non disponible"}

        if not service.thread_id:
            return {"error": "thread non démarré ou non identifiable"}

        try:
            proc = psutil.Process(os.getpid())
            for thread in proc.threads():
                if thread.id == service.thread_id:
                    cpu_time = round(thread.user_time + thread.system_time, 2)
                    duration = round(time.time() - service.start_time, 2)
                    memory_mb = round(proc.memory_info().rss / 1024 / 1024, 2)
                    restrying = self.restart_attempts.get(service.name, 0)
                    return TaskResource(
                        tid=service.thread_id,
                        cpu_time=cpu_time,
                        duration=duration,
                        memory_mb=memory_mb,
                        retrying=restrying,
                    )
        except Exception as e:
            logger.error(f"[ServiceManager] Erreur analyse ressource")
            logger.exception(e)
            return Error.Exception_Response(
                msg="ServiceManager on analyse ressource",
                type="error",
                extension=str(e),
            )

        return Error.Exception_Response(
            type="warning",
            msg="ServiceManager on analyse ressource",
            extension="not found thread",
        )

    def auto_restart(self, serviced):
        """
        Surveille les services et tente un redémarrage automatique
        en cas de crash, avec une limite de tentatives par service.
        """

        self.__monitor(
            serviced=serviced,
            interval=cfg.get("tasks", "interval"),
            max_retries=cfg.get("tasks", "max_retries"),
        )

    def __monitor(self, serviced: Any, interval: int, max_retries: int):
        logger.info(
            f"[ServiceManager] Auto-restart activé (max {max_retries} tentatives/service)"
        )
        while serviced.running:
            for name, service in list(self.services.items()):
                alive = service.thread and service.thread.is_alive()
                if not service.running or not alive:
                    count = self.restart_attempts.get(name, 0)
                    if count >= max_retries:
                        logger.error(
                            f"[AutoRestart] ✖ '{name}' a dépassé {max_retries} tentatives, arrêt du suivi."
                        )
                        continue
                    logger.warning(
                        f"[AutoRestart] ⚠ '{name}' inactif → tentative {count + 1}/{max_retries}"
                    )
                    try:
                        service.restart()
                        self.restart_attempts[name] = count + 1
                        logger.info(f"[AutoRestart] '{name}' relancé avec succès")
                    except Exception as e:
                        self.restart_attempts[name] = count + 1
                        logger.error(
                            f"[AutoRestart] ✖ Erreur lors du redémarrage de '{name}': {e}"
                        )
            time.sleep(interval)

    def reload(
        self,
    ):
        for _, service in list(self.services.items()):
            service.restart()
