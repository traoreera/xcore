"""
BreakingChangeDetector — Compare deux SchemaRegistry pour détecter les breaking changes.

Breaking changes détectés :
  - Action supprimée d'un plugin
  - Champ d'entrée supprimé
  - Type d'un champ d'entrée modifié
  - Champ de sortie supprimé
  - breaking_since déclaré explicitement (le plugin dit lui-même que c'est breaking)

Non-breaking (ignorés) :
  - Ajout d'un champ optionnel à l'entrée
  - Ajout d'un champ à la sortie
  - Changement de version sans breaking_since
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import ActionSchema, SchemaRegistry


@dataclass
class BreakingChange:
    plugin: str
    action: str
    kind: str  # "action_removed" | "field_removed" | "type_changed" | "explicit"
    field: str | None  # champ concerné (None pour action_removed / explicit)
    location: str  # "input" | "output" | "action"
    old_value: str | None
    new_value: str | None
    message: str

    def __str__(self) -> str:
        loc = f"[{self.location}]" if self.location else ""
        field = f".{self.field}" if self.field else ""
        return f"  ✗ {self.plugin}:{self.action}{field} {loc} — {self.message}"


class BreakingChangeDetector:
    """
    Compare un registry précédent (sauvegardé) avec le registry courant.

    Usage :
        from xcore.kernel.schema import BreakingChangeDetector, SchemaRegistry

        previous = SchemaRegistry.load(".xcore/schemas.json")
        current  = schema_registry   # le singleton rempli au boot

        detector = BreakingChangeDetector(previous, current)
        changes  = detector.detect()

        for change in changes:
            print(change)
    """

    def __init__(
        self,
        previous: "SchemaRegistry",
        current: "SchemaRegistry",
        plugin_filter: str | None = None,
    ) -> None:
        self._prev = previous
        self._curr = current
        self._filter = plugin_filter

    def detect(self) -> list[BreakingChange]:
        changes: list[BreakingChange] = []

        prev_schemas = {
            s.key: s
            for s in self._prev.all()
            if self._filter is None or s.plugin == self._filter
        }
        curr_schemas = {
            s.key: s
            for s in self._curr.all()
            if self._filter is None or s.plugin == self._filter
        }

        for key, prev in prev_schemas.items():
            if key not in curr_schemas:
                changes.append(
                    BreakingChange(
                        plugin=prev.plugin,
                        action=prev.action,
                        kind="action_removed",
                        field=None,
                        location="action",
                        old_value=prev.version,
                        new_value=None,
                        message=f"Action supprimée (était v{prev.version})",
                    )
                )
                continue

            curr = curr_schemas[key]
            changes.extend(self._compare(prev, curr))

        return changes

    def _compare(
        self, prev: "ActionSchema", curr: "ActionSchema"
    ) -> list[BreakingChange]:
        changes: list[BreakingChange] = []

        # Breaking déclaré explicitement par le plugin
        if curr.breaking_since and self._version_gt(curr.breaking_since, prev.version):
            changes.append(
                BreakingChange(
                    plugin=curr.plugin,
                    action=curr.action,
                    kind="explicit",
                    field=None,
                    location="action",
                    old_value=prev.version,
                    new_value=curr.version,
                    message=(
                        f"Breaking depuis v{curr.breaking_since} "
                        f"(ancienne version déployée : v{prev.version})"
                    ),
                )
            )

        # Champs supprimés ou dont le type a changé — input
        for fname, ftype in prev.input.items():
            if fname not in curr.input:
                changes.append(
                    BreakingChange(
                        plugin=curr.plugin,
                        action=curr.action,
                        kind="field_removed",
                        field=fname,
                        location="input",
                        old_value=ftype,
                        new_value=None,
                        message=f"Champ '{fname}' ({ftype}) supprimé de l'entrée",
                    )
                )
            elif curr.input[fname] != ftype:
                changes.append(
                    BreakingChange(
                        plugin=curr.plugin,
                        action=curr.action,
                        kind="type_changed",
                        field=fname,
                        location="input",
                        old_value=ftype,
                        new_value=curr.input[fname],
                        message=(
                            f"Type du champ '{fname}' modifié : "
                            f"{ftype} → {curr.input[fname]}"
                        ),
                    )
                )

        # Champs supprimés de la sortie
        for fname, ftype in prev.output.items():
            if fname not in curr.output:
                changes.append(
                    BreakingChange(
                        plugin=curr.plugin,
                        action=curr.action,
                        kind="field_removed",
                        field=fname,
                        location="output",
                        old_value=ftype,
                        new_value=None,
                        message=f"Champ '{fname}' ({ftype}) supprimé de la sortie",
                    )
                )

        return changes

    @staticmethod
    def _version_gt(v1: str, v2: str) -> bool:
        """Retourne True si v1 > v2 (comparaison semver simplifiée)."""

        def parts(v: str) -> tuple[int, ...]:
            try:
                return tuple(int(x) for x in v.strip().split("."))
            except ValueError:
                return (0,)

        return parts(v1) > parts(v2)
