import logging
from typing import Any

from integrations.crud.plugin import PluginsCrud
from integrations.db import get_db
from integrations.plManager import logger
from integrations.schemas.plugins import Plugin


class Repository:
    """Interface CRUD pour la gestion des plugins enregistrés en base."""

    def __init__(self, logger: logging.Logger | Any = logger) -> None:
        self.logger = logger
        self.db = PluginsCrud(db=next(get_db()))

    def get_all_active(self) -> list:
        return self.db.get_all_active()

    def get_all(self) -> list:

        return self.db.get_all()

    def add(self, plugin: Plugin) -> dict:
        return self.db.add(plugin)

    def enable(self, name: str) -> bool:
        return self.db.status(name, True)

    def disable(self, name: str) -> bool:
        return self.db.status(name, False)
