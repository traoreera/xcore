"""
───────────────
Canal IPC asynchrone entre le Core et un subprocess Sandboxed.
Protocole : JSON newline-delimited sur stdin/stdout du subprocess.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger("plManager.ipc")


class IPCError(Exception):
    """Erreur de communication avec le subprocess."""


class IPCTimeoutError(IPCError):
    """Le subprocess n'a pas répondu dans le délai imparti."""


class IPCProcessDead(IPCError):
    """Le subprocess est mort."""


@dataclass
class IPCResponse:
    success: bool
    data: dict
    raw: str = ""


class IPCChannel:
    """
    Encapsule la communication JSON stdin/stdout avec un asyncio.subprocess.
    Thread-safe via un asyncio.Lock (un seul appel à la fois par subprocess).
    """

    def __init__(
        self,
        process: asyncio.subprocess.Process,
        timeout: float = 10.0,
        max_output_size: int = 1024 * 512,
    ) -> None:
        self._process = process
        self._timeout = timeout
        self._max_output_size = max_output_size
        self._lock = asyncio.Lock()

    async def call(self, action: str, payload: dict) -> IPCResponse:
        if self._is_dead():
            raise IPCProcessDead("Le subprocess sandbox est mort")
        async with self._lock:
            return await self._send_and_receive(action, payload)

    async def _send_and_receive(self, action: str, payload: dict) -> IPCResponse:
        request_line = json.dumps({"action": action, "payload": payload}) + "\n"

        try:
            self._process.stdin.write(request_line.encode())
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise IPCProcessDead(f"Impossible d'écrire dans stdin : {e}") from e

        # FIX #1 — UnboundLocalError corrigé :
        # Le `except asyncio.TimeoutError` original faisait `raise ... from e`
        # mais `e` n'était défini que dans le bloc `except Exception as e` suivant
        # → UnboundLocalError garanti à l'exécution.
        # Correction : chaque bloc capture sa propre variable, pas de référence croisée.
        try:
            raw = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            # `from None` : supprime le contexte implicite, pas de variable externe.
            raise IPCTimeoutError(
                f"Pas de réponse du plugin dans {self._timeout}s"
            ) from None
        except Exception as exc:
            raise IPCError(f"Erreur lecture stdout : {exc}") from exc

        if not raw:
            raise IPCProcessDead("EOF inattendu sur stdout du subprocess")

        if len(raw) > self._max_output_size:
            raise IPCError(
                f"Réponse trop volumineuse ({len(raw)} octets > {self._max_output_size})"
            )

        raw_str = raw.decode("utf-8", errors="replace").strip()

        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError as exc:
            raise IPCError(
                f"Réponse JSON invalide : {exc} — reçu : {raw_str!r}"
            ) from exc

        return IPCResponse(
            success=data.get("status") == "ok",
            data=data,
            raw=raw_str,
        )

    def _is_dead(self) -> bool:
        return self._process.returncode is not None

    async def close(self) -> None:
        try:
            self._process.stdin.close()
            await self._process.stdin.wait_closed()
        except Exception:
            logger.warning("Impossible de fermer stdin du subprocess")