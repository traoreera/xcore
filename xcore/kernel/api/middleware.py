import logging
from importlib import import_module
from typing import Any, Callable

from fastapi import FastAPI

from ...configurations.sections import MiddlewareConfig


class Middlewares:
    def __init__(
        self, config: list[MiddlewareConfig], prototypes: Callable, event_bus: Any
    ) -> None:
        self._config = config
        self._prototypes = prototypes
        self._event_bus = event_bus

    def _build_instances(self, logger: logging.Logger) -> list[dict[str, Any]]:
        instances = []
        for mddw in self._config:
            if not mddw.module:
                logger.warning(
                    "Middleware '%s' ignoré : module non spécifié", mddw.name
                )
                continue
            parts = mddw.module.split(":")
            if len(parts) != 2:
                logger.warning(
                    "Middleware '%s' ignoré : format module invalide (attendu 'pkg.mod:Class')",
                    mddw.name,
                )
                continue
            try:
                mod = import_module(parts[0])
                cls = getattr(mod, parts[1])
            except (ImportError, AttributeError) as exc:
                logger.error(
                    "Middleware '%s' : impossible de charger '%s' — %s",
                    mddw.name,
                    mddw.module,
                    exc,
                )
                continue

            config = {}
            for param in mddw.config:
                if not param.name:
                    continue
                if param.type == "internal":
                    # Passe un callable () → service, résolu à la requête
                    svc_name = param.value
                    config[param.name] = lambda n=svc_name: self._prototypes(n)
                elif param.type == "events":
                    # Passe un callable () → event bus, résolu à la requête
                    config[param.name] = lambda: self._event_bus
                else:
                    config[param.name] = param.value
            instances.append({"cls": cls, "config": config, "name": mddw.name})
        return instances

    def configure(self, app: FastAPI | None, logger: logging.Logger) -> None:
        """Enregistre les middlewares — DOIT être appelé avant le démarrage de l'app."""
        if app is None or not self._config:
            return
        for mdw in self._build_instances(logger=logger):
            app.add_middleware(mdw["cls"], **mdw["config"])
            logger.info("Middleware '%s' ajouté (%s)", mdw["name"], mdw["cls"].__name__)
