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
        handler: PluginHandler | None,
        **kwargs,
    ) -> dict:
        """Exécute la logique du middleware."""
        ...


class MiddlewarePipeline:
    """Gère une chaîne de middlewares."""

    def __init__(self, middlewares: List[Middleware], final_handler: Callable):
        self._middlewares = middlewares
        self._final_handler = final_handler
        # Compilation de la chaîne au démarrage pour minimiser l'overhead.
        self._compiled_chain = self._compile_pipeline(
            middlewares, final_handler
        )

    def _compile_pipeline(
        self, middlewares: List[Middleware], final_handler: Callable
    ) -> Callable:
        """
        Compile la chaîne de middlewares en une série de closures imbriquées.
        Évite de redéfinir la fonction récursive _chain à chaque appel.
        """

        async def _final_step(
            p_name: str, act: str, pay: dict, h: PluginHandler | None, **kw
        ) -> dict:
            return await final_handler(p_name, act, pay, handler=h, **kw)

        current = _final_step
        for mw in reversed(middlewares):

            def _make_step(m: Middleware, next_step: Callable):
                async def _step(
                    p_name: str,
                    act: str,
                    pay: dict,
                    h: PluginHandler | None,
                    **kw,
                ) -> dict:
                    # On passe 'next_step' et 'h' directement pour éviter
                    # la création d'une lambda (closure) à chaque appel.
                    return await m(p_name, act, pay, next_step, h, **kw)

                return _step

            current = _make_step(mw, current)
        return current

    async def execute(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        *,
        handler: PluginHandler | None = None,
        **kwargs,
    ) -> dict:
        """Démarre l'exécution de la chaîne via la version compilée."""
        return await self._compiled_chain(
            plugin_name, action, payload, handler, **kwargs
        )
