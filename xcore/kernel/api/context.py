"""
context.py — Contexte riche injecté dans chaque plugin.

PluginContext remplace le simple dict de services de la v1.
Il donne accès aux services, à l'event bus, aux hooks,
aux variables d'environnement et à la config du plugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginContext:
    """
    Contexte injecté dans chaque plugin Trusted au moment du chargement.

    Attributs:
        name:     nom du plugin
        services: dict partagé des services (BDD, cache, autres plugins…)
        events:   EventBus — émettre/souscrire des événements
        hooks:    HookManager — hooks prioritaires avec wildcards
        env:      variables d'environnement résolues depuis plugin.yaml
        config:   bloc `extra` du manifeste (config arbitraire du plugin)
    """

    name: str
    services: dict[str, Any] = field(default_factory=dict)
    events: Any = None  # EventBus
    hooks: Any = None  # HookManager
    env: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    def get_service(self, name: str) -> Any:
        """Accès sécurisé à un service avec message d'erreur clair."""
        svc = self.services.get(name)
        if svc is None:
            raise KeyError(
                f"[{self.name}] Service '{name}' indisponible. "
                f"Disponibles : {sorted(self.services.keys())}"
            )
        return svc

    def has_service(self, name: str) -> bool:
        return name in self.services

    def __repr__(self) -> str:
        return (
            f"<PluginContext plugin='{self.name}' "
            f"services={sorted(self.services.keys())}>"
        )
