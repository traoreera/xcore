from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("integrations.extensions")


class ServiceStatus(str, Enum):
    """
    status du service
    """

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    CRASHED = "crashed"
    STOPPED = "stopped"


@dataclass
class ServiceWorkerState:
    """
    Etat d'un service.
    """

    name: str
    status: ServiceStatus = ServiceStatus.IDLE
    restarts: int = 0
    last_error: Optional[str] = None
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _scheduler: Optional[Any] = field(default=None, repr=False)
