"""
contracts/base_plugin.py
─────────────────────────
Contrat interface commun à tous les plugins (Trusted et Sandboxed).

- BasePlugin  : Protocol structurel — aucun import du core requis dans le plugin
- TrustedBase : ABC optionnelle pour les Trusted qui veulent l'injection de services
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from multiprocessing import Manager
from typing import Any, Protocol, runtime_checkable

# ──────────────────────────────────────────────
# Contrat universel (Protocol — duck typing)
# ──────────────────────────────────────────────


@runtime_checkable
class BasePlugin(Protocol):
    """
    Interface minimale que tout plugin doit respecter.
    Pas besoin d'hériter — le duck typing suffit.
    """

    async def handle(self, action: str, payload: dict) -> dict:
        """
        Point d'entrée unique du plugin.

        Args:
            action  : identifiant de l'action demandée (ex: "ping", "write_file")
            payload : données associées à l'action

        Returns:
            dict avec au minimum {"status": "ok"|"error"}
        """
        ...


# ──────────────────────────────────────────────
# ABC pour plugins Trusted (injection de services)
# ──────────────────────────────────────────────


class TrustedBase(ABC):
    """
    Classe de base optionnelle pour les plugins Trusted.
    Permet l'injection des services internes du Core.
    """

    def __init__(self, services: dict[str, Any] | None = None) -> None:
        """
        Args:
            services: dict des services core injectés par le PluginManager
                    ex: {"db": db_instance, "cache": cache_instance}
        """
        self._services: dict[str, Any] = services or {}

    def get_service(self, name: str) -> Any:
        """Récupère un service core par son nom."""
        if name not in self._services:
            raise KeyError(
                f"Service '{name}' non disponible. "
                f"Services injectés : {list(self._services.keys())}"
            )
        return self._services[name]

    @abstractmethod
    async def handle(self, action: str, payload: dict) -> dict:
        """Point d'entrée unique — même contrat que BasePlugin."""
        ...

    # ── Hooks de cycle de vie (optionnels, à override si besoin) ──

    async def on_load(self) -> None:
        """Appelé juste après le chargement du plugin."""

    async def on_unload(self) -> None:
        """Appelé avant le déchargement du plugin."""

    async def on_reload(self) -> None:
        """Appelé lors d'un rechargement à chaud."""

    async def env_variable(self, manifest: dict) -> dict:
        """enviromment set on app"""


# ──────────────────────────────────────────────
# Réponses standardisées
# ──────────────────────────────────────────────


def ok(data: dict | None = None, **kwargs) -> dict:
    """Construit une réponse succès standardisée."""
    return {"status": "ok", **(data or {}), **kwargs}


def error(msg: str, code: str | None = None, **kwargs) -> dict:
    """Construit une réponse erreur standardisée."""
    result = {"status": "error", "msg": msg}
    if code:
        result["code"] = code
    result |= kwargs
    return result
