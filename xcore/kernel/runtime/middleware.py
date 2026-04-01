"""
middleware.py — Pipeline de middlewares pour les appels de plugins.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .loader import PluginHandler

logger = logging.getLogger("xcore.runtime.middleware")


class Middleware(ABC):
    """Classe de base pour les middlewares de supervision."""

    @abstractmethod
    async def __call__(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        next_call: Callable,
        *,
        handler: PluginHandler | None = None,
        **kwargs
    ) -> dict:
        """Exécute la logique du middleware."""
        ...


class MiddlewarePipeline:
    """Gère une chaîne de middlewares."""

    def __init__(self, middlewares: List[Middleware], final_handler: Callable):
        self._middlewares = middlewares
        self._final_handler = final_handler
        self._compiled_chain = self._build_chain()

    def _build_chain(self) -> Callable:
        """
        Compile la chaîne de middlewares en une seule fonction imbriquée.
        Cela évite de recréer la chaîne à chaque appel.
        """
        handler = self._final_handler

        for middleware in reversed(self._middlewares):
            handler = self._bind(middleware, handler)

        return handler

    def _bind(self, middleware: Middleware, next_step: Callable) -> Callable:
        """Lie un middleware à l'étape suivante de la chaîne."""

        async def wrapper(
            plugin_name: str,
            action: str,
            payload: dict,
            *,
            handler: PluginHandler | None = None,
            **kwargs
        ) -> dict:
            return await middleware(
                plugin_name,
                action,
                payload,
                next_step,
                handler=handler,
                **kwargs
            )

        return wrapper

    async def execute(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        *,
        handler: PluginHandler | None = None,
        **kwargs
    ) -> dict:
        """Exécute la chaîne pré-compilée."""
        return await self._compiled_chain(
            plugin_name, action, payload, handler=handler, **kwargs
        )
