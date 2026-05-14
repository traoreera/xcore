"""
SchemaRegistry — Registre central des schémas d'actions de plugins.

Chaque action décorée avec @schema y est enregistrée automatiquement.
Le registry permet de :
  - valider les entrées/sorties au dispatch
  - persister les schémas (JSON) pour détecter les breaking changes entre déploiements
  - exposer la liste des actions versionnées via le CLI
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("xcore.schema.registry")


@dataclass
class ActionSchema:
    plugin: str
    action: str
    version: str
    input: dict[str, str]  # {field_name: type_name}
    output: dict[str, str]  # {field_name: type_name}
    deprecated_fields: dict[str, str] = field(default_factory=dict)  # {field: reason}
    breaking_since: str | None = None
    description: str = ""

    @property
    def key(self) -> str:
        return f"{self.plugin}:{self.action}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionSchema":
        return cls(**d)


class SchemaRegistry:
    """
    Registre singleton des schémas d'actions.

    Usage :
        from xcore.kernel.schema import schema_registry

        # Enregistrer (fait par @schema)
        schema_registry.register("auth", "create_user", schema)

        # Lire
        s = schema_registry.get("auth", "create_user")

        # Persister pour comparaison future
        schema_registry.save(".xcore/schemas.json")
        previous = SchemaRegistry.load(".xcore/schemas.json")
    """

    def __init__(self) -> None:
        self._schemas: dict[str, ActionSchema] = {}

    def register(self, schema: ActionSchema) -> None:
        self._schemas[schema.key] = schema
        logger.debug("Schema enregistré : %s v%s", schema.key, schema.version)

    def get(self, plugin: str, action: str) -> ActionSchema | None:
        return self._schemas.get(f"{plugin}:{action}")

    def get_by_key(self, key: str) -> ActionSchema | None:
        return self._schemas.get(key)

    def all(self) -> list[ActionSchema]:
        return list(self._schemas.values())

    def for_plugin(self, plugin: str) -> list[ActionSchema]:
        return [s for s in self._schemas.values() if s.plugin == plugin]

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {key: s.to_dict() for key, s in self._schemas.items()}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Schemas sauvegardés : %s (%d actions)", path, len(data))

    @classmethod
    def load(cls, path: str | Path) -> "SchemaRegistry":
        path = Path(path)
        registry = cls()
        if not path.exists():
            return registry
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, d in data.items():
            try:
                registry._schemas[key] = ActionSchema.from_dict(d)
            except Exception as exc:
                logger.warning("Schema ignoré '%s' : %s", key, exc)
        logger.info("Schemas chargés : %s (%d actions)", path, len(registry._schemas))
        return registry

    def summary(self) -> dict[str, Any]:
        return {
            "total": len(self._schemas),
            "plugins": sorted({s.plugin for s in self._schemas.values()}),
            "actions": [
                {"key": s.key, "version": s.version, "breaking_since": s.breaking_since}
                for s in sorted(self._schemas.values(), key=lambda s: s.key)
            ],
        }


# Singleton global — importé par @schema et par le CLI
schema_registry = SchemaRegistry()
