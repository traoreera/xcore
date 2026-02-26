"""
ipc.py — Canal IPC JSON newline-delimited entre le Core et un subprocess Sandboxed.
Fix #1 v1 intégré : UnboundLocalError sur asyncio.TimeoutError corrigé.
"""
from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger("xcore.sandbox.ipc")


class IPCError(Exception): pass
class IPCTimeoutError(IPCError): pass
class IPCProcessDead(IPCError): pass


@dataclass
class IPCResponse:
    success: bool
    data: dict
    raw: str = ""


class IPCChannel:
    """Canal IPC thread-safe via asyncio.Lock."""

    def __init__(self, process: asyncio.subprocess.Process,
                 timeout: float = 10.0, max_output_size: int = 512 * 1024) -> None:
        self._process        = process
        self._timeout        = timeout
        self._max_output_size = max_output_size
        self._lock           = asyncio.Lock()

    async def call(self, action: str, payload: dict) -> IPCResponse:
        if self._is_dead():
            raise IPCProcessDead("Subprocess mort")
        async with self._lock:
            return await self._send_recv(action, payload)

    async def _send_recv(self, action: str, payload: dict) -> IPCResponse:
        line = json.dumps({"action": action, "payload": payload}) + "\n"
        try:
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise IPCProcessDead(f"Écriture stdin impossible : {e}") from e

        # FIX #1 : chaque bloc except gère sa propre variable, pas de référence croisée
        try:
            raw = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            raise IPCTimeoutError(f"Pas de réponse dans {self._timeout}s") from None
        except Exception as exc:
            raise IPCError(f"Lecture stdout : {exc}") from exc

        if not raw:
            raise IPCProcessDead("EOF inattendu sur stdout")
        if len(raw) > self._max_output_size:
            raise IPCError(f"Réponse trop volumineuse ({len(raw)} octets)")

        raw_str = raw.decode("utf-8", errors="replace").strip()
        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError as exc:
            raise IPCError(f"JSON invalide : {exc} — reçu : {raw_str!r}") from exc

        return IPCResponse(success=data.get("status") == "ok", data=data, raw=raw_str)

    def _is_dead(self) -> bool:
        return self._process.returncode is not None

    async def close(self) -> None:
        try:
            self._process.stdin.close()
            await self._process.stdin.wait_closed()
        except Exception:
            pass
