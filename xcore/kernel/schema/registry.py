"""
SchemaRegistry — Registre central des schémas d'actions de plugins.

Chaque action décorée avec @action y est enregistrée automatiquement, que
@schema soit empilé dessous ou pas — une action sans @schema y apparaît avec
input/output vides mais permissions/permission_groups renseignés s'ils sont
déclarés. Le registry permet de :
  - valider les entrées/sorties au dispatch
  - persister les schémas (JSON) pour détecter les breaking changes entre déploiements
  - exposer la liste des actions versionnées via le CLI
  - servir de catalogue complet (schéma + permissions) pour un consommateur
    externe (génération de tools LLM, audit...) sans instancier chaque plugin
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..observability import get_logger

logger = get_logger("xcore.schema.registry")


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
    # JSON Schema complet (champs imbriqués, défauts, contraintes...) produit par
    # le Model pydantic réel construit dans @schema — {} si l'action n'a pas de
    # schéma d'entrée/sortie. `input`/`output` ci-dessus restent la source pour
    # BreakingChangeDetector (comparaison type-par-type) ; ces deux champs sont
    # pour les consommateurs externes (génération de tools LLM, OpenAPI, etc.)
    # qui ont besoin de la forme complète, pas juste du nom du type.
    input_json_schema: dict[str, Any] = field(default_factory=dict)
    output_json_schema: dict[str, Any] = field(default_factory=dict)
    # Miroir de fn._xcore_action_permissions / _xcore_action_permission_groups
    # (@action(permissions=..., permission_groups=...), voir sdk/decorators.py).
    # Dupliqué ici pour qu'un consommateur externe (catalogue d'outils LLM,
    # audit, doc...) lise permissions ET schéma pour TOUTE action depuis ce
    # seul registre — sans instancier le LifecycleManager de chaque plugin
    # (seule autre source : LifecycleManager.get_action_permissions()/
    # get_action_permission_groups(), qui exige une instance de plugin vivante
    # et reste la source d'autorité pour ActionPermissionMiddleware).
    permissions: list[str] = field(default_factory=list)
    permission_groups: list[list[str]] = field(default_factory=list)
    # Miroir de fn._xcore_action_side_effect (@action(side_effect=...)) —
    # "read" | "write" | "outbound" | None. Axe orthogonal aux permissions :
    # dit quel risque représente l'action une fois l'appel autorisé, pas qui
    # peut l'appeler. Purement déclaratif ici aussi — xcore n'en fait rien,
    # c'est un consommateur externe (ex : génération de tools LLM) qui décide
    # si une action sans side_effect déclaré doit être traitée comme la plus
    # risquée avant de l'exposer comme tool auto-approuvé.
    side_effect: str | None = None

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
        logger.debug("schema registered", key=schema.key, version=schema.version)

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
        logger.info("schemas saved", path=str(path), actions=len(data))

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
                logger.warning("schema skipped", key=key, error=str(exc))
        logger.info("schemas loaded", path=str(path), actions=len(registry._schemas))
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
