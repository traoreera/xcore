from sqlalchemy import and_
from sqlalchemy.orm import Session

import plugins
from manager.models.plugins import PluginsModels
from manager.schemas.plugins import Delete, Plugin, Update
from manager.tools.trasactional import Transactions


class PluginsCrud:
    def __init__(self, db: Session):
        self.db = db

    @Transactions.transactional
    def add(self, plugin_add: Plugin):

        if (
            self.db.query(PluginsModels)
            .filter(PluginsModels.name == plugin_add.name)
            .first()
        ):

            return {
                "type": "warning",
                "msg": f"Plugin '{plugin_add.name}' already exists",
            }

        plugin = PluginsModels(plugin=plugin_add)
        self.db.add(plugin)
        self.db.flush()
        return {
            "type": "info",
            "msg": f"Success to add plugin '{plugin_add.name}', activate it",
            "plugin": plugin,
        }

    @Transactions.transactional
    def delete(self, plugin: Delete):
        try:
            deleted_count = (
                self.db.query(PluginsModels)
                .filter(
                    and_(
                        PluginsModels.name == plugin.name, PluginsModels.id == plugin.id
                    )
                )
                .delete(synchronize_session=False)
            )
            if deleted_count:
                return {
                    "type": "info",
                    "msg": f"Success to delete plugin '{plugin.name}'",
                }
            return {
                "type": "warning",
                "msg": f"No plugin found to delete: '{plugin.name}'",
            }
        except Exception as e:
            return {
                "type": "warning",
                "msg": f"Error deleting plugin '{plugin.name}'",
                "exception": str(e),
            }

    @Transactions.transactional
    def update(self, plug: Delete, data: Update):
        # Récupérer l'instance existante
        plugin_instance = self._get(plug.name, plug.id)

        if not plugin_instance:
            return {"type": "warning", "msg": f"Plugin introuvable : {plug.name}"}

        # CORRECT : On génère le dictionnaire des données envoyées
        # Utilisez .model_dump si vous êtes sur Pydantic v2+
        update_data = data.model_dump(exclude_unset=True)

        # Mise à jour des attributs
        for key, value in update_data.items():
            if hasattr(plugin_instance, key):
                setattr(plugin_instance, key, value)

        self.db.flush()
        return {
            "type": "info",
            "msg": f"Succès de la mise à jour du plugin '{plugin_instance.name}'",
            "plugin": plugin_instance,
        }

    def get(self, name: str):
        plugin = self.db.query(PluginsModels).filter(PluginsModels.name == name).first()
        return plugin.response() if plugin else None

    def get_all(self, active: bool | None = None):
        query = self.db.query(PluginsModels)
        if active is not None:
            query = query.filter(PluginsModels.active == active)
        return [plugin.response() for plugin in query.all()]

    def get_all_active(self):
        return self.get_all(active=True)

    def get_all_not_active(self):
        return self.get_all(active=False)

    def status(self, name: str, active: bool):
        return (
            True
            if self.db.query(PluginsModels)
            .filter(PluginsModels.name == name)
            .update({"active": active})
            == 1
            else False
        )

    def close_db(self):
        self.db.close()

    def get_alls(self):
        return [plugs for plugs in self.db.query(PluginsModels).all()]

    def _get(self, name: str, id: str):
        return (
            self.db.query(PluginsModels)
            .filter(and_(PluginsModels.name == name, PluginsModels.id == id))
            .first()
        )
