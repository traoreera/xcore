from typing import Any

from sqlalchemy.orm import session

from ..crud.plugin import PluginsCrud
from ..db import get_db
from ..plManager import logger
from ..schemas.plugins import Plugin

from . import logging


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
