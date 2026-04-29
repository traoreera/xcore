"""
middleware_registry.py — Registry for managing and creating middleware pipelines.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .middleware import Middleware, MiddlewarePipeline

logger = logging.getLogger("xcore.runtime.middleware_registry")


class MiddlewareRegistry:
    """
    Registry for middleware factories.
    Allows decoupling the creation of the middleware pipeline from the supervisor.
    """

    def __init__(self) -> None:
        # factory: (context_dict) -> Middleware
        self._factories: dict[str, Callable[[dict[str, Any]], "Middleware"]] = {}

    def register(
        self, name: str, factory: Callable[[dict[str, Any]], "Middleware"]
    ) -> None:
        """Registers a middleware factory."""
        self._factories[name] = factory
        logger.debug(f"Middleware factory registered: {name}")

    def create_pipeline(
        self, names: list[str], context: dict[str, Any], final_handler: Callable
    ) -> "MiddlewarePipeline":
        """
        Creates a MiddlewarePipeline using the registered factories.
        """
        from .middleware import MiddlewarePipeline

        middlewares = []
        for name in names:
            if name in self._factories:
                try:
                    middleware = self._factories[name](context)
                    middlewares.append(middleware)
                except Exception as e:
                    logger.error(f"Error creating middleware '{name}': {e}")
            else:
                logger.warning(f"Middleware factory not found: {name}")

        return MiddlewarePipeline(middlewares=middlewares, final_handler=final_handler)
