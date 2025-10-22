from sqlalchemy.orm import session


from ..schemas.plugins import Plugin
from manager.db import get_db

from ..crud.plugin import PluginsCrud
from . import get_logger, logging


class Repository:
    """Interface CRUD pour la gestion des plugins enregistrés en base."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or get_logger(__name__)

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
