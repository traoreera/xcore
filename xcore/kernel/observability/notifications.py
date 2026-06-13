"""
notifications.py — Système de notification pour les alertes.

Consomme l'événement `anomaly.detected` et envoie des notifications
via les backends configurés (Log, Webhooks, etc.).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..events.bus import EventBus
    from ...configurations.sections import NotificationConfig

from . import get_logger

logger = get_logger("xcore.observability.notifications")


class AlertNotifier:
    """
    Envoie des notifications externes lors d'anomalies détectées.

    Usage:
        notifier = AlertNotifier(events, config.notifications)
        await notifier.start()
    """

    def __init__(self, events: "EventBus", config: "NotificationConfig") -> None:
        self._events = events
        self._config = config
        self._httpx_client: Any | None = None

    async def start(self) -> None:
        """S'abonne aux anomalies."""
        if not self._config.enabled:
            return

        self._events.subscribe("anomaly.detected", self._on_anomaly)
        logger.info("alert notifier started", backends=self._config.backends)

    async def stop(self) -> None:
        if self._httpx_client:
            await self._httpx_client.aclose()
            self._httpx_client = None

    async def _on_anomaly(self, event) -> None:
        data = event.data
        plugin = data.get("plugin", "unknown")
        error_count = data.get("error_count", 0)

        msg = f"🚨 [XCORE] Anomaly detected in plugin '{plugin}': {error_count} errors in the last window."

        tasks = []
        for backend in self._config.backends:
            if backend == "log":
                tasks.append(self._notify_log(msg, data))
            elif backend == "webhook":
                tasks.append(self._notify_webhooks(msg, data))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _notify_log(self, msg: str, data: dict) -> None:
        logger.error(msg, **data)

    async def _notify_webhooks(self, msg: str, data: dict) -> None:
        if not self._config.webhooks:
            return

        import httpx

        if self._httpx_client is None:
            self._httpx_client = httpx.AsyncClient(timeout=5.0)

        for name, cfg in self._config.webhooks.items():
            if not cfg.url:
                continue

            try:
                # Payload générique (format Slack-compatible par défaut)
                payload = {
                    "text": msg,
                    "attachments": [
                        {
                            "color": "danger",
                            "fields": [
                                {
                                    "title": "Plugin",
                                    "value": data.get("plugin"),
                                    "short": True,
                                },
                                {
                                    "title": "Errors",
                                    "value": str(data.get("error_count")),
                                    "short": True,
                                },
                                {
                                    "title": "Threshold",
                                    "value": str(data.get("threshold")),
                                    "short": True,
                                },
                            ],
                        }
                    ],
                }

                resp = await self._httpx_client.post(
                    cfg.url, json=payload, headers=cfg.headers
                )
                resp.raise_for_status()
                logger.debug("webhook notification sent", name=name)
            except Exception as e:
                logger.error("webhook notification failed", name=name, error=str(e))
