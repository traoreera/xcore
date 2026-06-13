"""
alerts.py — Détection d'anomalies et alerting in-app.

Surveille les événements `plugin.*.error` et émet `anomaly.detected`
si un seuil est franchi.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..events.bus import EventBus

from . import get_logger

logger = get_logger("xcore.observability.alerts")


@dataclass
class AnomalyThreshold:
    """Seuils d'alerte pour un plugin."""

    max_errors: int = 10
    window_seconds: int = 60


class AnomalyDetector:
    """
    Surveille le taux d'erreur des plugins en temps réel.

    Usage:
        detector = AnomalyDetector(events)
        detector.configure("shop", max_errors=5, window_seconds=30)
        await detector.start()
    """

    def __init__(self, events: "EventBus") -> None:
        self._events = events
        # plugin_name -> deque des timestamps d'erreurs
        self._error_windows: dict[str, deque[float]] = {}
        # plugin_name -> threshold
        self._thresholds: dict[str, AnomalyThreshold] = {}
        # plugin_name -> timestamp de la dernière alerte (anti-spam)
        self._last_alert: dict[str, float] = {}

    def configure(
        self, plugin_name: str, max_errors: int = 10, window_seconds: int = 60
    ) -> None:
        self._thresholds[plugin_name] = AnomalyThreshold(max_errors, window_seconds)
        if plugin_name not in self._error_windows:
            self._error_windows[plugin_name] = deque()

    async def start(self) -> None:
        """S'abonne aux erreurs de plugins."""
        self._events.subscribe("plugin.*.error", self._on_plugin_error)
        logger.info("anomaly detector started")

    async def _on_plugin_error(self, event) -> None:
        plugin_name = event.name.split(".")[1]
        now = time.monotonic()

        if plugin_name not in self._error_windows:
            self._error_windows[plugin_name] = deque()

        window = self._error_windows[plugin_name]
        window.append(now)

        # Nettoyage de la fenêtre
        threshold = self._thresholds.get(plugin_name, AnomalyThreshold())
        while window and window[0] < now - threshold.window_seconds:
            window.popleft()

        # Vérification du seuil
        if len(window) >= threshold.max_errors:
            await self._trigger_alert(plugin_name, len(window), threshold)

    async def _trigger_alert(
        self, plugin_name: str, error_count: int, threshold: AnomalyThreshold
    ) -> None:
        now = time.monotonic()
        # Anti-spam : max une alerte par minute par plugin
        if now - self._last_alert.get(plugin_name, 0) < 60:
            return

        self._last_alert[plugin_name] = now
        logger.error(
            "anomaly detected",
            plugin=plugin_name,
            error_count=error_count,
            window_s=threshold.window_seconds,
        )

        await self._events.emit(
            "anomaly.detected",
            {
                "type": "high_error_rate",
                "plugin": plugin_name,
                "error_count": error_count,
                "threshold": threshold.max_errors,
                "window": threshold.window_seconds,
            },
        )
