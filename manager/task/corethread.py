import os
import threading
import time

from ..plManager import logger

try:
    import psutil
except ImportError:
    psutil = None  # psutil est facultatif mais recommandé


class ThreadedService:
    def __init__(self, target, name="ThreadedService"):
        self.target = target
        self.name = name
        self.running = False
        self.thread = None
        self.thread_id = None
        self.start_time = None

    def _run(self):
        self.running = True
        self.start_time = time.time()
        self.thread_id = threading.get_native_id()

        logger.info(f"[{self.name}] → Démarrage du service (TID: {self.thread_id})")
        try:
            self.target(self)
        except Exception as e:
            logger.error(f"[{self.name}] ✖ Erreur : {e}")
            return
        logger.warning(f"[{self.name}] ← Service arrêté")

    def start(self):
        if self.running:
            logger.info(f"[{self.name}] ⚠ Le service est déjà en cours")
            return
        self.thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self.thread.start()

    def stop(self, callback=None):
        if not self.running:
            logger.warning(f"[{self.name}] ⚠ Le service n'est pas en cours")
            return
        logger.info(f"[{self.name}] ⏹ Arrêt demandé")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        if callback:
            logger.info(f"[{self.name}] ☑ Callback d'arrêt en cours...")
            callback()
        logger.info(f"[{self.name}] ✅ Service arrêté")

    def restart(self, callback=None):
        logger.info(f"[{self.name}] 🔁 Redémarrage du service...")
        self.stop(callback=callback)
        time.sleep(0.5)
        self.start()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class ServiceManager:
    def __init__(self):
        self.services = {}

    def add_service(self, name, target):
        if name in self.services:
            logger.warning(f"⚠ Le service '{name}' existe déjà.")
            return
        service = ThreadedService(target=target, name=name)
        self.services[name] = service
        service.start()

    def remove_service(self, name):
        if name not in self.services:
            logger.warning(f"⚠ Le service '{name}' n'existe pas.")
            return False
        self.services[name].stop()
        del self.services[name]
        logger.info(f"Service '{name}' supprimé.")

        return True

    def list_services(self):
        taks = []
        for name, service in self.services.items():
            status = "running" if service.running else "stopped"
            taks.append({"name": name, "service": service, "status": status})
        return taks

    def stop_all(self):
        for service in list(self.services.values()):
            service.stop()

    def stop_service(self, name):
        if name in self.services:
            self.services[name].stop()
            logger.info(f"Service '{name}' arrêté.")
        else:
            logger.warning(f"⚠ Le service '{name}' n'existe pas.")

    def restart(self, name):
        if name in self.services:
            self.services[name].restart()
            logger.info(f"Service '{name}' redémarré.")
            return True
        else:
            logger.warning(f"⚠ Le service '{name}' n'existe pas.")
            return False

    def get_service_resource_usage(self, service):
        """Retourne les statistiques de ressource du service (thread)"""
        if not psutil or not service.thread_id:
            logger.warning(
                "psutil non disponible. les taches sont execute mai sans tid(task id)"
            )
            return {"error": "psutil non disponible ou thread non démarré"}

        try:
            proc = psutil.Process(os.getpid())
            for thread in proc.threads():
                if thread.id == service.thread_id:
                    return {
                        "tid": service.thread_id,
                        "cpu_time": round(thread.user_time + thread.system_time, 2),
                        "duration": round(time.time() - service.start_time, 2),
                        "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 2),
                    }
        except Exception as e:
            return {"error": str(e)}

        return {"error": "thread non trouvé"}
