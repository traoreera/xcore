from typing import Any

from ..decorators import logger


class AutoDispatchMixin:
    """
    Mixin qui génère automatiquement handle() à partir des méthodes décorées @action.

    Usage:
        class Plugin(AutoDispatchMixin, TrustedBase):

            @action("greet")
            async def greet(self, payload: dict) -> dict:
                return ok(msg="hello")

        # handle("greet", {}) → appelle self.greet({})
        # handle("unknown", {}) → {"status": "error", "code": "unknown_action"}
    """

    _action_map_built: bool = False

    def _build_action_map(self) -> None:
        """Pré-construit un dict action_name → method pour un dispatch O(1)."""
        self._action_map: dict[str, Any] = {}
        for attr_name in dir(self.__class__):
            method = getattr(self.__class__, attr_name, None)
            if not callable(method):
                continue
            action_name = getattr(method, "_xcore_action", None)
            if action_name:
                self._action_map[action_name] = getattr(self, attr_name)
        self._action_map_built = True

    def _register_schemas(self, plugin_name: str) -> None:
        """Enregistre tous les schémas @schema de ce plugin dans le SchemaRegistry."""
        from xcore.kernel.schema.registry import ActionSchema, schema_registry

        for attr_name in dir(self.__class__):
            method = getattr(self.__class__, attr_name, None)
            if not callable(method):
                continue
            action_name = getattr(method, "_xcore_action", None)
            schema_meta = getattr(method, "_xcore_schema", None)
            if action_name and schema_meta:
                schema_registry.register(
                    ActionSchema(
                        plugin=plugin_name,
                        action=action_name,
                        version=schema_meta["version"],
                        input=schema_meta["input"],
                        output=schema_meta["output"],
                        deprecated_fields=schema_meta["deprecated_fields"],
                        breaking_since=schema_meta["breaking_since"],
                        description=schema_meta["description"],
                    )
                )

    async def handle(self, action_name: str, payload: dict) -> dict:
        from xcore.kernel.api.contract import error

        if not self._action_map_built:
            self._build_action_map()

        method = self._action_map.get(action_name)
        if method is not None:
            # Avertissement si des champs dépréciés sont utilisés
            schema_meta = getattr(method, "_xcore_schema", None)
            if schema_meta and schema_meta.get("deprecated_fields"):
                for dep_field, reason in schema_meta["deprecated_fields"].items():
                    if dep_field in payload:
                        logger.warning(
                            "Plugin action '%s:%s' — champ déprécié '%s' utilisé : %s",
                            getattr(self, "name", "?"),
                            action_name,
                            dep_field,
                            reason,
                        )
            return await method(payload)  # type: ignore

        available = list(self._action_map.keys())
        return error(
            f"Action '{action_name}' inconnue. Disponibles : {available}",
            "unknown_action",
        )

    def action_registry(self) -> list[dict]:
        """Retourne la liste des actions déclarées avec leurs schémas."""
        if not self._action_map_built:
            self._build_action_map()
        result = []
        for action_name, method in self._action_map.items():
            entry: dict = {"action": action_name}
            schema_meta = getattr(method, "_xcore_schema", None)
            if schema_meta:
                entry.update(schema_meta)
            result.append(entry)
        return result
