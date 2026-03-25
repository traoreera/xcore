"""
---Permission Evaluation Engine
The PermissionEngine is the singleton that:
    1. Loads PolicySets from manifests at startup
    2. Responds to authorization requests on every plugin call
    3. Emits audit events (allow/deny)
"""

from __future__ import annotations

import logging

from .policies import PolicyEffect, PolicySet
from collections import deque
logger = logging.getLogger("xcore.permissions.engine")


class PermissionDenied(Exception):
    """Raise when a permission check fails."""


class PermissionEngine:
    """
    Central engine for permission evaluation.

    Usage:
    ```python
        engine = PermissionEngine()
        engine.load_from_manifest("my_plugin", manifest.permissions)

        # verify
        engine.check("my_plugin", resource="db.users", action="write")
        # → raise PermissionDenied if not allowed

        # Test without lever
        ok = engine.allows("my_plugin", "db.users", "write")
    ```
    """

    def __init__(self, events=None, max_audit=100_000) -> None:
        self._policies: dict[str, PolicySet] = {}
        self._events = events
        self._audit_log:  deque[dict] = deque(maxlen=max_audit)
        self._cache: dict[tuple[str, str, str], PolicyEffect] = {}

    def load_from_manifest(
        self, plugin_name: str, raw_permissions: list[dict] | None
    ) -> None:
        """load policies from manifest"""
        self._cache.clear()  # Invalidate cache on policy change
        if not raw_permissions:
            self._policies[plugin_name] = PolicySet.deny_all(plugin_name)
            logger.debug(f"[{plugin_name}] Aucune permission déclarée → DENY ALL")
        else:
            ps = PolicySet.from_list(plugin_name, raw_permissions)
            self._policies[plugin_name] = ps
            logger.debug(f"[{plugin_name}] {len(ps.policies)} règle(s) chargée(s)")

    def grant_all(self, plugin_name: str) -> None:
        """Grant all permissions to a plugin."""
        self._cache.clear()  # Invalidate cache on policy change
        self._policies[plugin_name] = PolicySet.allow_all(plugin_name)

    def check(self, plugin_name: str, resource: str, action: str) -> None:
        """
        verify permission and raise PermissionDenied if not allowed.
        """
        effect = self._evaluate(plugin_name, resource, action)
        self._audit(plugin_name, resource, action, effect)
        if effect == PolicyEffect.DENY:
            raise PermissionDenied(
                f"[{plugin_name}] Accès refusé : {action} sur '{resource}'"
            )

    def allows(self, plugin_name: str, resource: str, action: str) -> bool:
        """Returns True if the plugin is allowed to perform the action on the resource."""
        try:
            self.check(plugin_name, resource, action)
            return True
        except PermissionDenied:
            return False

    def _evaluate(self, plugin_name: str, resource: str, action: str) -> PolicyEffect:
        # Check cache first
        cache_key = (plugin_name, resource, action)
        if cache_key in self._cache:
            return self._cache[cache_key]

        ps = self._policies.get(plugin_name)
        if ps is None:
            logger.warning(f"[{plugin_name}] Aucune policy chargée → DENY")
            effect = PolicyEffect.DENY
        else:
            effect = ps.evaluate(resource, action)

        self._cache[cache_key] = effect
        return effect

    def _audit(
        self, plugin_name: str, resource: str, action: str, effect: PolicyEffect
    ) -> None:
        entry = {
            "plugin": plugin_name,
            "resource": resource,
            "action": action,
            "effect": effect.value,
        }
        self._audit_log.append(entry)
        if effect == PolicyEffect.DENY:
            logger.warning(f"DENY [{plugin_name}] {action} on '{resource}'")
        if self._events:
            self._events.emit_sync(f"permission.{effect.value}", entry)

    def audit_log(self, plugin_name: str | None = None, limit: int = 100) -> list[dict]:
        """Returns the audit log, filtered by plugin name if provided, up to the limit."""
        from itertools import islice

        # Iterate in reverse to get the latest entries first
        it = reversed(self._audit_log)
        if plugin_name:
            it = (e for e in it if e["plugin"] == plugin_name)

        # Slice to the limit and return in chronological order
        results = list(islice(it, limit))
        results.reverse()
        return results

    def status(self) -> dict:
        return {
            "plugins": {name: ps.to_list() for name, ps in self._policies.items()},
            "audit_entries": len(self._audit_log),
        }
