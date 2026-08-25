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

        for attr_name in dir(self):
            method = getattr(self, attr_name, None)
            if (
                callable(method)
                and getattr(method, "_xcore_action", None) == action_name
            ):
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

        available = [
            getattr(getattr(self, a), "_xcore_action")
            for a in dir(self)
            if callable(getattr(self, a, None))
            and hasattr(getattr(self, a), "_xcore_action")
        ]
        return error(
            f"Action '{action_name}' inconnue. Disponibles : {available}",
            "unknown_action",
        )

    def action_registry(self) -> list[dict]:
        """Retourne la liste des actions déclarées avec leurs schémas."""
        result = []
        for attr_name in dir(self):
            method = getattr(self, attr_name, None)
            if not callable(method):
                continue
            action_name = getattr(method, "_xcore_action", None)
            if not action_name:
                continue
            entry: dict = {"action": action_name}
            schema_meta = getattr(method, "_xcore_schema", None)
            if schema_meta:
                entry.update(schema_meta)
            result.append(entry)
        return result
