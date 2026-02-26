"""
engine.py — Moteur d'évaluation des permissions.

Le PermissionEngine est le singleton qui :
  1. Charge les PolicySet depuis les manifestes au démarrage
  2. Répond aux requêtes d'autorisation à chaque appel de plugin
  3. Émet des événements d'audit (allow/deny)
"""
from __future__ import annotations

import logging
from typing import Any

from .policies import PolicyEffect, PolicySet

logger = logging.getLogger("xcore.permissions.engine")


class PermissionDenied(Exception):
    """Levée quand une permission est refusée."""


class PermissionEngine:
    """
    Moteur de permissions centralisé.

    Usage:
        engine = PermissionEngine()
        engine.load_from_manifest("my_plugin", manifest.permissions)

        # Vérification
        engine.check("my_plugin", resource="db.users", action="write")
        # → lève PermissionDenied si refusé

        # Test sans lever
        ok = engine.allows("my_plugin", "db.users", "write")
    """

    def __init__(self, events=None) -> None:
        self._policies: dict[str, PolicySet] = {}
        self._events = events
        self._audit_log: list[dict] = []

    def load_from_manifest(self, plugin_name: str, raw_permissions: list[dict] | None) -> None:
        """Charge les policies d'un plugin depuis son manifeste."""
        if not raw_permissions:
            # Sans policies déclarées → deny all (fail-closed)
            self._policies[plugin_name] = PolicySet.deny_all(plugin_name)
            logger.debug(f"[{plugin_name}] Aucune permission déclarée → DENY ALL")
        else:
            ps = PolicySet.from_list(plugin_name, raw_permissions)
            self._policies[plugin_name] = ps
            logger.debug(f"[{plugin_name}] {len(ps.policies)} règle(s) chargée(s)")

    def grant_all(self, plugin_name: str) -> None:
        """Accordé pour les plugins Trusted avec strict_trusted=False."""
        self._policies[plugin_name] = PolicySet.allow_all(plugin_name)

    def check(self, plugin_name: str, resource: str, action: str) -> None:
        """
        Vérifie une permission. Lève PermissionDenied si refusé.
        À appeler dans les services avant d'exécuter une opération.
        """
        effect = self._evaluate(plugin_name, resource, action)
        self._audit(plugin_name, resource, action, effect)
        if effect == PolicyEffect.DENY:
            raise PermissionDenied(
                f"[{plugin_name}] Accès refusé : {action} sur '{resource}'"
            )

    def allows(self, plugin_name: str, resource: str, action: str) -> bool:
        """Retourne True si autorisé, False sinon (pas d'exception)."""
        try:
            self.check(plugin_name, resource, action)
            return True
        except PermissionDenied:
            return False

    def _evaluate(self, plugin_name: str, resource: str, action: str) -> PolicyEffect:
        ps = self._policies.get(plugin_name)
        if ps is None:
            logger.warning(f"[{plugin_name}] Aucune policy chargée → DENY")
            return PolicyEffect.DENY
        return ps.evaluate(resource, action)

    def _audit(self, plugin_name: str, resource: str, action: str, effect: PolicyEffect) -> None:
        entry = {
            "plugin": plugin_name, "resource": resource,
            "action": action, "effect": effect.value
        }
        self._audit_log.append(entry)
        if effect == PolicyEffect.DENY:
            logger.warning(f"DENY [{plugin_name}] {action} on '{resource}'")
        if self._events:
            self._events.emit_sync(f"permission.{effect.value}", entry)

    def audit_log(self, plugin_name: str | None = None, limit: int = 100) -> list[dict]:
        log = self._audit_log if not plugin_name else [
            e for e in self._audit_log if e["plugin"] == plugin_name
        ]
        return log[-limit:]

    def status(self) -> dict:
        return {
            "plugins": {name: ps.to_list() for name, ps in self._policies.items()},
            "audit_entries": len(self._audit_log),
        }
