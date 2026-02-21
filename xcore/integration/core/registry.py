"""
Service Registry — enregistrement et résolution centralisée de tous les services.
Supporte l'injection de dépendances, le lazy loading et les scopes.
"""

from __future__ import annotations

import inspect
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, TypeVar

logger = logging.getLogger("integrations.registry")

T = TypeVar("T")


class ServiceScope(str, Enum):
    SINGLETON = "singleton"  # Une seule instance pour toute la durée de vie
    TRANSIENT = "transient"  # Nouvelle instance à chaque résolution
    SCOPED = "scoped"  # Une instance par scope (ex: par requête HTTP)


class ServiceDescriptor:
    """Décrit comment un service doit être créé et géré."""

    def __init__(
        self,
        name: str,
        factory: Callable[..., Any],
        scope: ServiceScope = ServiceScope.SINGLETON,
        tags: list[str] | None = None,
    ):
        self.name = name
        self.factory = factory
        self.scope = scope
        self.tags = tags or []
        self._instance: Optional[Any] = None

    def resolve(self, registry: "ServiceRegistry") -> Any:
        if self.scope == ServiceScope.SINGLETON:
            if self._instance is None:
                self._instance = self._create(registry)
            return self._instance
        return self._create(registry)

    def _create(self, registry: "ServiceRegistry") -> Any:
        sig = inspect.signature(self.factory)
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.annotation != inspect.Parameter.empty:
                try:
                    kwargs[param_name] = registry.resolve(param.annotation)
                except KeyError:
                    pass
        return self.factory(**kwargs)


class ServiceRegistry:
    """
    Registre centralisé de tous les services de l'application.

    Usage:
        registry = ServiceRegistry()

        # Enregistrement simple
        registry.register("db", lambda: Database(url="sqlite:///./app.db"))

        # Enregistrement par classe
        registry.register_class(MyService, scope=ServiceScope.SINGLETON)

        # Résolution
        db = registry.resolve("db")
        db = registry.resolve(Database)
    """

    def __init__(self):
        self._descriptors: Dict[str, ServiceDescriptor] = {}
        self._aliases: Dict[str, str] = {}
        self._scoped: Dict[str, Any] = {}

    # ── ENREGISTREMENT ────────────────────────────────────────

    def register(
        self,
        name: str,
        factory: Callable[..., Any],
        scope: ServiceScope = ServiceScope.SINGLETON,
        tags: list[str] | None = None,
        aliases: list[str] | None = None,
    ) -> "ServiceRegistry":
        """Enregistre un service avec une factory."""
        self._descriptors[name] = ServiceDescriptor(name, factory, scope, tags)
        for alias in aliases or []:
            self._aliases[alias] = name
        logger.debug(f"Service enregistré: {name} [{scope.value}]")
        return self

    def register_instance(
        self,
        name: str,
        instance: Any,
        aliases: list[str] | None = None,
    ) -> "ServiceRegistry":
        """Enregistre une instance déjà créée (toujours singleton)."""
        descriptor = ServiceDescriptor(name, lambda: instance, ServiceScope.SINGLETON)
        descriptor._instance = instance
        self._descriptors[name] = descriptor
        for alias in aliases or []:
            self._aliases[alias] = name
        logger.debug(f"Instance enregistrée: {name}")
        return self

    def register_class(
        self,
        cls: Type[T],
        name: Optional[str] = None,
        scope: ServiceScope = ServiceScope.SINGLETON,
        tags: list[str] | None = None,
    ) -> "ServiceRegistry":
        """Enregistre une classe comme service (auto-injection des dépendances)."""
        service_name = name or cls.__name__
        self.register(
            service_name, cls, scope=scope, tags=tags, aliases=[cls.__qualname__]
        )
        return self

    # ── RÉSOLUTION ────────────────────────────────────────────

    def resolve(self, name_or_type: str | Type[T]) -> Any:
        """Résout un service par nom ou par type."""
        name = name_or_type if isinstance(name_or_type, str) else name_or_type.__name__
        # Alias
        name = self._aliases.get(name, name)

        if name not in self._descriptors:
            raise KeyError(
                f"Service non trouvé: '{name}'. "
                f"Disponibles: {list(self._descriptors.keys())}"
            )

        return self._descriptors[name].resolve(self)

    def resolve_all_by_tag(self, tag: str) -> list[Any]:
        """Résout tous les services ayant un tag donné."""
        return [
            desc.resolve(self)
            for desc in self._descriptors.values()
            if tag in desc.tags
        ]

    def get(self, name: str, default: Any = None) -> Any:
        """Résolution souple — retourne default si le service est absent."""
        try:
            return self.resolve(name)
        except KeyError:
            return default

    # ── INTROSPECTION ─────────────────────────────────────────

    def is_registered(self, name: str) -> bool:
        return name in self._descriptors or name in self._aliases

    def list_services(self) -> Dict[str, str]:
        return {name: desc.scope.value for name, desc in self._descriptors.items()}

    def __repr__(self) -> str:
        return f"<ServiceRegistry services={list(self._descriptors.keys())}>"


# Singleton global
_registry: Optional[ServiceRegistry] = None


def get_registry() -> ServiceRegistry:
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry
