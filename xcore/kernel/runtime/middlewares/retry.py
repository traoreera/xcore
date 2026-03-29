"""
retry.py — Middleware de retry pour les appels de plugins.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from ..middleware import Middleware

logger = logging.getLogger("xcore.runtime.middlewares.retry")


class RetryMiddleware(Middleware):
    """Gère les tentatives de re-exécution en cas d'échec."""

    def __init__(self, loader: Any):
        self._loader = loader

    async def __call__(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        next_call: Callable,
        **kwargs
    ) -> dict:
        handler = self._loader.get(plugin_name)
        manifest = getattr(handler, "manifest", None)
        retry_cfg = getattr(manifest, "runtime", None)

        max_attempts = (
            getattr(getattr(retry_cfg, "retry", None), "max_attempts", 1)
            if retry_cfg
            else 1
        )
        backoff = (
            getattr(getattr(retry_cfg, "retry", None), "backoff_seconds", 0.0)
            if retry_cfg
            else 0.0
        )

        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = await next_call(plugin_name, action, payload, **kwargs)
                if isinstance(result, dict) and result.get("status") == "error":
                     # On ne retry que si c'est une exception,
                     # les erreurs "métier" ne sont pas retry par défaut
                     return result
                return result
            except Exception as e:
                last_err = e
                if attempt < max_attempts:
                    logger.warning(
                        f"[{plugin_name}] Tentative {attempt} échouée, retry dans {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)

        logger.error(f"[{plugin_name}] Toutes les tentatives échouées : {last_err}")
        return {"status": "error", "msg": str(last_err), "code": "all_retries_failed"}
