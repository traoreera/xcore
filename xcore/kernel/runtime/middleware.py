"""
middleware.py — Pipeline de middlewares pour les appels de plugins.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, List

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
        **kwargs,
    ) -> dict:
        """Exécute la logique du middleware."""
        ...


class MiddlewarePipeline:
    """Gère une chaîne de middlewares."""

    def __init__(self, middlewares: List[Middleware], final_handler: Callable):
        self._middlewares = middlewares
        self._final_handler = final_handler

    async def execute(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        *,
        handler: PluginHandler | None = None,
        **kwargs,
    ) -> dict:
        """Démarre l'exécution de la chaîne."""

        async def _chain(
            index: int, p_name: str, act: str, pay: dict, h: PluginHandler | None, **kw
        ) -> dict:
            if index < len(self._middlewares):
                middleware = self._middlewares[index]
                return await middleware(
                    p_name,
                    act,
                    pay,
                    lambda pn, a, pl, **k: _chain(index + 1, pn, a, pl, h, **k),
                    handler=h,
                    **kw,
                )
            return await self._final_handler(p_name, act, pay, handler=h, **kw)

        return await _chain(0, plugin_name, action, payload, handler, **kwargs)
