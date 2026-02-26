"""
validator.py — Validation statique des blocs permissions dans les manifestes.
"""
from __future__ import annotations
from typing import Any


class PermissionValidationError(Exception):
    pass


VALID_EFFECTS = {"allow", "deny"}
_REQUIRED_KEYS = {"resource"}


class PermissionValidator:
    """
    Valide le bloc `permissions:` d'un manifeste plugin.

    Usage:
        v = PermissionValidator()
        v.validate("my_plugin", raw_permissions_list)  # lève PermissionValidationError si invalide
    """

    def validate(self, plugin_name: str, raw: list[dict[str, Any]] | None) -> None:
        if raw is None:
            return   # absence = deny all, valide

        if not isinstance(raw, list):
            raise PermissionValidationError(
                f"[{plugin_name}] 'permissions' doit être une liste, reçu : {type(raw).__name__}"
            )

        for i, rule in enumerate(raw):
            self._validate_rule(plugin_name, i, rule)

    @staticmethod
    def _validate_rule(plugin_name: str, idx: int, rule: dict) -> None:
        if not isinstance(rule, dict):
            raise PermissionValidationError(
                f"[{plugin_name}] permissions[{idx}] doit être un dict"
            )

        for key in _REQUIRED_KEYS:
            if key not in rule:
                raise PermissionValidationError(
                    f"[{plugin_name}] permissions[{idx}] : clé obligatoire manquante : '{key}'"
                )

        effect = rule.get("effect", "allow")
        if effect not in VALID_EFFECTS:
            raise PermissionValidationError(
                f"[{plugin_name}] permissions[{idx}] : effect invalide '{effect}'. "
                f"Valeurs : {sorted(VALID_EFFECTS)}"
            )

        actions = rule.get("actions", ["*"])
        if not isinstance(actions, list) or not actions:
            raise PermissionValidationError(
                f"[{plugin_name}] permissions[{idx}] : 'actions' doit être une liste non vide"
            )
