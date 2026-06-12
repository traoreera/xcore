"""
retry.py — Middleware de tentatives (retry) pour les appels de plugins.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from ..observability import get_logger
from .middleware import Middleware

logger = get_logger("xcore.runtime.middleware.retry")


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
        handler,
        **kwargs,
    ) -> dict:
        manifest = getattr(handler, "manifest", None) if handler else None
        retry_cfg = getattr(manifest, "runtime", None) if manifest else None

        retry_params = getattr(retry_cfg, "retry", None) if retry_cfg else None
        max_attempts = getattr(retry_params, "max_attempts", 1) if retry_params else 1
        backoff = getattr(retry_params, "backoff_seconds", 0.0) if retry_params else 0.0

        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = await next_call(
                    plugin_name, action, payload, handler, **kwargs
                )

                if (
                    isinstance(result, dict)
                    and result.get("status") == "error"
                    and result.get("code") == "exception"
                ):
                    raise Exception(result.get("msg", "Unknown error"))

                return result

            except Exception as e:
                last_err = e
                if attempt < max_attempts:
                    logger.warning(
                        "call failed, retrying",
                        plugin=plugin_name,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        backoff_s=backoff,
                        error=str(e),
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)

        logger.error(
            "all retries exhausted",
            plugin=plugin_name,
            attempts=max_attempts,
            error=str(last_err),
        )
        return {
            "status": "error",
            "msg": str(last_err),
            "code": "all_retries_failed",
            "attempts": max_attempts,
        }
