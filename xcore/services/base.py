"""
base.py — Contrat commun pour tous les services xcore.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class ServiceStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPED = "stopped"


class BaseService(ABC):
    """
    ABC pour les services xcore.

    Chaque service implémente :
      - init()         → connexion, warmup
      - shutdown()     → fermeture propre
      - health_check() → (ok: bool, msg: str)
      - status()       → dict de métriques/état

    Usage dans une classe concrète :
        class MyService(BaseService):
            name = "my_service"

            async def init(self):
                self._conn = await connect(...)
                self._status = ServiceStatus.READY

            async def shutdown(self):
                await self._conn.close()
                self._status = ServiceStatus.STOPPED

            async def health_check(self) -> tuple[bool, str]:
                try:
                    await self._conn.ping()
                    return True, "OK"
                except Exception as e:
                    return False, str(e)

            def status(self) -> dict:
                return {"name": self.name, "status": self._status.value}
    """

    name: str = "service"

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    @abstractmethod
    async def init(self) -> None: ...

    @abstractmethod
    async def shutdown(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]: ...

    @abstractmethod
    def status(self) -> dict[str, Any]: ...

    @property
    def is_ready(self) -> bool:
        return self._status == ServiceStatus.READY

    @property
    def service_status(self) -> ServiceStatus:
        return self._status
