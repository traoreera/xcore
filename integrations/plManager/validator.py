from typing import Any

from . import logger


class Validator:
    """Valide la structure et les métadonnées d’un plugin."""

    def __init__(self) -> None:

        self.logger = logger
        return

    def __call__(self, module: Any):

        return self.valdiate(module)

    def _validate_plugin(self, mod: Any) -> bool:
        name = getattr(mod, "__name__", "unknown")
        info = getattr(mod, "PLUGIN_INFO", None)

        if info is None:
            self.logger.warning(f"{name}: PLUGIN_INFO manquant")
            return False

        required = {"name", "version", "author"}
        if not required.issubset(info.keys()):
            self.logger.warning(
                f"{name}: clés PLUGIN_INFO manquantes: {required - info.keys()}"
            )
            return False

        if not hasattr(mod, "Plugin") or not hasattr(mod.Plugin, "run"):
            self.logger.warning(f"{name}: classe Plugin ou méthode run manquante")
            return False

        return True

    def valdiate(self, module: Any) -> bool:
        return self._validate_plugin(module)
