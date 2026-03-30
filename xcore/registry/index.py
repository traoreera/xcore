"""
index.py — Registre global des plugins chargés.

Maintient un index name → handler avec métadonnées.
Permet la découverte, l'introspection et les dépendances inter-plugins.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..configurations.sections import PluginConfig

logger = logging.getLogger("xcore.registry")


class PluginRegistry:
    """
    Registre central des plugins.

    Séparé du PluginSupervisor pour respecter le principe
    de responsabilité unique :
      - Supervisor : runtime (appels, reload, crash)
      - Registry   : découverte, métadonnées, dépendances

    Usage:
        registry = PluginRegistry(config)
        registry.register("my_plugin", handler)

        info = registry.get_info("my_plugin")
        all  = registry.all_plugins()
        deps = registry.dependents_of("core")
    """

    def __init__(self, config: "PluginConfig | None" = None) -> None:
        self._config = config
        self._entries: dict[str, dict[str, Any]] = {}
        # service_name -> metadata
        self._exported_services: dict[str, dict[str, Any]] = {}

    def register(self, name: str, handler: Any, metadata: dict | None = None) -> None:
        manifest = getattr(handler, "manifest", None)
        self._entries[name] = {
            "name": name,
            "handler": handler,
            "version": getattr(manifest, "version", "0.0.0"),
            "mode": (
                getattr(manifest, "execution_mode", {}).value
                if hasattr(getattr(manifest, "execution_mode", None), "value")
                else "unknown"
            ),
            "requires": getattr(manifest, "requires", []),
            "description": getattr(manifest, "description", ""),
            "author": getattr(manifest, "author", "unknown"),
            **(metadata or {}),
        }
        logger.debug(f"[registry] enregistré : '{name}'")

    def unregister(self, name: str) -> None:
        # Nettoie aussi les services exportés par ce plugin
        self._exported_services = {
            s: meta
            for s, meta in self._exported_services.items()
            if meta.get("plugin") != name
        }
        self._entries.pop(name, None)

    def register_service(
        self,
        plugin_name: str,
        service_name: str,
        service_obj: Any,
        metadata: dict | None = None,
    ) -> None:
        """Enregistre un service exporté par un plugin."""
        self._exported_services[service_name] = {
            "plugin": plugin_name,
            "obj": service_obj,
            **(metadata or {}),
        }
        logger.debug(
            f"[registry] service '{service_name}' enregistré par '{plugin_name}'"
        )

    def get_service(self, service_name: str, requester: str | None = None) -> Any:
        """
        Récupère un service avec vérification de scoping.
        Scoping supporté :
          - 'public' (défaut) : accessible par tous les plugins.
          - 'private' : accessible uniquement par le plugin propriétaire.
        """
        if service_name not in self._exported_services:
            raise KeyError(f"Service '{service_name}' non trouvé.")

        meta = self._exported_services[service_name]
        scope = meta.get("scope", "public")
        owner = meta.get("plugin")

        # Vérification du scope private
        if scope == "private" and requester != owner:
            raise PermissionError(
                f"Accès refusé au service privé '{service_name}'. "
                f"Propriétaire: '{owner}', Requérant: '{requester}'"
            )

        return meta["obj"]

    def list_services(self) -> list[dict]:
        return [
            {
                "name": name,
                "plugin": meta["plugin"],
                "scope": meta.get("scope", "public"),
            }
            for name, meta in self._exported_services.items()
        ]

    def has(self, name: str) -> bool:
        return name in self._entries

    def get_info(self, name: str) -> dict[str, Any]:
        if name not in self._entries:
            raise KeyError(
                f"Plugin '{name}' non enregistré. "
                f"Disponibles : {sorted(self._entries.keys())}"
            )
        entry = dict(self._entries[name])
        entry.pop("handler", None)  # ne pas exposer le handler brut
        return entry

    def all_plugins(self) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in e.items() if k != "handler"}
            for e in self._entries.values()
        ]

    def all_names(self) -> list[str]:
        return sorted(self._entries.keys())

    def dependents_of(self, plugin_name: str) -> list[str]:
        """Retourne les plugins qui dépendent de plugin_name."""
        return [
            name
            for name, e in self._entries.items()
            if plugin_name in e.get("requires", [])
        ]

    def required_by(self, plugin_name: str) -> list[str]:
        """Alias lisible de dependents_of."""
        return self.dependents_of(plugin_name)

    def plugins_by_mode(self, mode: str) -> list[str]:
        return [name for name, e in self._entries.items() if e.get("mode") == mode]

    def search(self, query: str) -> list[dict]:
        """Recherche par nom, description ou auteur (case-insensitive)."""
        q = query.lower()
        results = []
        for name, e in self._entries.items():
            if (
                q in name.lower()
                or q in e.get("description", "").lower()
                or q in e.get("author", "").lower()
            ):
                results.append({k: v for k, v in e.items() if k != "handler"})
        return results

    def summary(self) -> dict:
        total = len(self._entries)
        by_mode: dict[str, int] = {}
        for e in self._entries.values():
            m = e.get("mode", "unknown")
            by_mode[m] = by_mode.get(m, 0) + 1
        return {"total": total, "by_mode": by_mode}
