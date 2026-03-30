"""
retry.py — Middleware de tentatives (retry) pour les appels de plugins.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable
from ..middleware import Middleware

logger = logging.getLogger("xcore.runtime.middleware.retry")


class RetryMiddleware(Middleware):
    """
    Middleware gérant les tentatives en cas d'échec d'un appel.
    Utilise la configuration 'runtime.retry' du manifeste du plugin.
    """

    async def __call__(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        next_call: Callable,
        *,
        handler=None,
        **kwargs
    ) -> dict:
        manifest = getattr(handler, "manifest", None) if handler else None
        retry_cfg = getattr(manifest, "runtime", None) if manifest else None

        # Extraction sécurisée des paramètres de retry
        retry_params = getattr(retry_cfg, "retry", None) if retry_cfg else None
        max_attempts = getattr(retry_params, "max_attempts", 1) if retry_params else 1
        backoff = getattr(retry_params, "backoff_seconds", 0.0) if retry_params else 0.0

        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = await next_call(plugin_name, action, payload, **kwargs)

                # Si le résultat indique une erreur de type exception capturée par le handler
                if isinstance(result, dict) and result.get("status") == "error" and result.get("code") == "exception":
                    raise Exception(result.get("msg", "Unknown error"))

                return result

            except Exception as e:
                last_err = e
                if attempt < max_attempts:
                    logger.warning(
                        f"[{plugin_name}] Tentative {attempt}/{max_attempts} échouée, "
                        f"retry dans {backoff}s : {e}"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0) # Exponential backoff plafonné

        logger.error(f"[{plugin_name}] Toutes les tentatives ({max_attempts}) ont échoué : {last_err}")
        return {
            "status": "error",
            "msg": str(last_err),
            "code": "all_retries_failed",
            "attempts": max_attempts
        }
