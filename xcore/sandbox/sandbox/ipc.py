"""
sandbox/ipc.py
───────────────
Canal IPC asynchrone entre le Core et un subprocess Sandboxed.
Protocole : JSON newline-delimited sur stdin/stdout du subprocess.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
import logging
logger = logging.getLogger("plManager.ipc")


# ──────────────────────────────────────────────
# Erreurs IPC
# ──────────────────────────────────────────────

class IPCError(Exception):
    """Erreur de communication avec le subprocess."""

class IPCTimeoutError(IPCError):
    """Le subprocess n'a pas répondu dans le délai imparti."""

class IPCProcessDead(IPCError):
    """Le subprocess est mort."""


# ──────────────────────────────────────────────
# Résultat d'un appel IPC
# ──────────────────────────────────────────────

@dataclass
class IPCResponse:
    success:  bool
    data:     dict
    raw:      str = ""


# ──────────────────────────────────────────────
# Canal IPC
# ──────────────────────────────────────────────

class IPCChannel:
    """
    Encapsule la communication JSON stdin/stdout avec un asyncio.subprocess.
    Thread-safe via un asyncio.Lock (un seul appel à la fois par subprocess).
    """

    def __init__(
        self,
        process:         asyncio.subprocess.Process,
        timeout:         float = 10.0,
        max_output_size: int   = 1024 * 512,  # 512 KB max par réponse
    ) -> None:
        self._process         = process
        self._timeout         = timeout
        self._max_output_size = max_output_size
        self._lock            = asyncio.Lock()

    # ──────────────────────────────────────────
    # Appel principal
    # ──────────────────────────────────────────

    async def call(self, action: str, payload: dict) -> IPCResponse:
        """
        Envoie une requête au subprocess et attend sa réponse.
        Thread-safe, non-bloquant, avec timeout.

        Raises:
            IPCProcessDead   si le process est mort
            IPCTimeoutError  si le process ne répond pas à temps
            IPCError         pour toute autre erreur de communication
        """
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

        try:
            raw = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            raise IPCTimeoutError(
                f"Pas de réponse du plugin dans {self._timeout}s"
            ) from e
        except Exception as e:
            raise IPCError(f"Erreur lecture stdout : {e}") from e 

        if not raw:
            raise IPCProcessDead("EOF inattendu sur stdout du subprocess")

        if len(raw) > self._max_output_size:
            raise IPCError(
                f"Réponse trop volumineuse ({len(raw)} octets > "
                f"{self._max_output_size})"
            )

        raw_str = raw.decode("utf-8", errors="replace").strip()

        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError as e:
            raise IPCError(f"Réponse JSON invalide : {e} — reçu : {raw_str!r}") from e 

        return IPCResponse(
            success=data.get("status") == "ok",
            data=data,
            raw=raw_str,
        )

    # ──────────────────────────────────────────
    # Utilitaires
    # ──────────────────────────────────────────

    def _is_dead(self) -> bool:
        return self._process.returncode is not None

    async def close(self) -> None:
        """Ferme stdin proprement pour signaler la fin au subprocess."""
        try:
            self._process.stdin.close()
            await self._process.stdin.wait_closed()
        except Exception:
            logger.warning("Impossible de fermer stdin du subprocess")