"""
process_manager.py — Gestionnaire de subprocess Sandboxed.
Fix #2 v1 intégré : _handle_crash() itératif, pas récursif.
"""
from __future__ import annotations
import asyncio
import contextlib
import logging
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from .isolation import DiskWatcher, DiskQuotaExceeded
from .ipc import IPCChannel, IPCProcessDead, IPCResponse

logger = logging.getLogger("xcore.sandbox.process_manager")


class ProcessState(Enum):
    STOPPED    = "stopped"
    STARTING   = "starting"
    RUNNING    = "running"
    RESTARTING = "restarting"
    FAILED     = "failed"


@dataclass
class SandboxConfig:
    timeout: float        = 10.0
    max_restarts: int     = 3
    restart_delay: float  = 1.0
    startup_timeout: float = 5.0


class SandboxProcessManager:
    """
    Gère le cycle de vie d'un subprocess plugin Sandboxed.

    Fix #2 v1 : _handle_crash() est entièrement itératif (boucle while)
    et ne s'appelle plus jamais via start() → plus de RecursionError.
    """

    def __init__(self, manifest, config: SandboxConfig | None = None) -> None:
        self.manifest   = manifest
        self.config     = config or SandboxConfig()
        self._process: asyncio.subprocess.Process | None = None
        self._channel:  IPCChannel | None    = None
        self._state     = ProcessState.STOPPED
        self._restarts  = 0
        self._started_at: float | None = None
        self._watch_task:  asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None
        data_dir = manifest.plugin_dir / "data"
        self._disk = DiskWatcher(data_dir, manifest.resources.max_disk_mb)

    @property
    def state(self) -> ProcessState: return self._state

    @property
    def is_available(self) -> bool: return self._state == ProcessState.RUNNING

    @property
    def uptime(self) -> float | None:
        return None if self._started_at is None else time.monotonic() - self._started_at

    async def start(self) -> None:
        if self._state == ProcessState.FAILED:
            raise RuntimeError(f"Plugin {self.manifest.name} en état FAILED")
        if self._state == ProcessState.RUNNING:
            return
        self._state = ProcessState.STARTING
        await self._spawn()
        await self._ping_check()
        self._state = ProcessState.RUNNING
        self._started_at = time.monotonic()
        self._restarts = 0
        self._watch_task = asyncio.create_task(
            self._watch_loop(), name=f"watch-{self.manifest.name}"
        )
        hc = self.manifest.runtime.health_check
        if hc.enabled:
            self._health_task = asyncio.create_task(
                self._health_loop(hc.interval_seconds, hc.timeout_seconds),
                name=f"health-{self.manifest.name}",
            )
        logger.info(f"[{self.manifest.name}] ✅ Subprocess démarré (PID={self._process.pid})")

    async def _spawn(self) -> None:
        worker_path = Path(__file__).parent / "worker.py"
        venv_py = self.manifest.plugin_dir / "venv" / "bin" / "python"
        python  = str(venv_py) if venv_py.exists() else sys.executable
        sandbox_home = (self.manifest.plugin_dir / ".sandbox_home").resolve()
        sandbox_home.mkdir(parents=True, exist_ok=True)

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(sandbox_home),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "_SANDBOX_MAX_MEM_MB": str(self.manifest.resources.max_memory_mb),
        }
        env |= self.manifest.env

        self._process = await asyncio.create_subprocess_exec(
            python, str(worker_path), str(self.manifest.plugin_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.manifest.plugin_dir),
            env=env,
        )
        self._channel = IPCChannel(self._process, timeout=self.manifest.resources.timeout_seconds)

    async def _ping_check(self) -> None:
        hc = self.manifest.runtime.health_check
        timeout = max(hc.timeout_seconds, self.config.startup_timeout)
        try:
            resp = await asyncio.wait_for(self._channel.call("ping", {}), timeout=timeout)
            if not resp.success:
                raise RuntimeError(f"Ping échoué : {resp.data}")
        except asyncio.TimeoutError as e:
            await self._kill()
            raise RuntimeError(f"Pas de réponse au ping dans {timeout}s") from e

    async def call(self, action: str, payload: dict) -> IPCResponse:
        if not self.is_available:
            raise RuntimeError(f"Plugin {self.manifest.name} non disponible")
        try:
            self._disk.check(self.manifest.name)
        except DiskQuotaExceeded as e:
            return IPCResponse(success=False,
                               data={"status": "error", "msg": str(e), "code": "disk_quota"})
        try:
            return await self._channel.call(action, payload)
        except IPCProcessDead:
            await self._handle_crash()
            raise

    async def _watch_loop(self) -> None:
        if not self._process:
            return
        code = await self._process.wait()
        if self._state == ProcessState.STOPPED:
            return
        logger.warning(f"[{self.manifest.name}] Subprocess terminé (code={code})")
        if self._process.stderr:
            with contextlib.suppress(Exception):
                err = await asyncio.wait_for(self._process.stderr.read(2048), timeout=1.0)
                if err:
                    logger.error(f"[{self.manifest.name}] stderr: {err.decode('utf-8', 'replace').strip()}")
        await self._handle_crash()

    async def _health_loop(self, interval: float, timeout: float) -> None:
        await asyncio.sleep(interval)
        while self._state == ProcessState.RUNNING:
            try:
                resp = await asyncio.wait_for(self._channel.call("ping", {}), timeout=timeout)
                if not resp.success:
                    logger.warning(f"[{self.manifest.name}] Health dégradé")
            except asyncio.TimeoutError:
                logger.error(f"[{self.manifest.name}] Health timeout")
                await self._handle_crash()
                return
            except Exception as e:
                logger.error(f"[{self.manifest.name}] Health erreur : {e}")
                await self._handle_crash()
                return
            await asyncio.sleep(interval)

    # FIX #2 v1 : itératif, plus récursif
    async def _handle_crash(self) -> None:
        if self._state in (ProcessState.RESTARTING, ProcessState.FAILED, ProcessState.STOPPED):
            return   # anti-réentrance

        self._state = ProcessState.RESTARTING

        while self._restarts < self.config.max_restarts:
            self._restarts += 1
            delay = min(self.config.restart_delay * (2 ** (self._restarts - 1)), 60.0)
            logger.info(f"[{self.manifest.name}] Restart {self._restarts}/{self.config.max_restarts} dans {delay:.1f}s")
            await asyncio.sleep(delay)

            for task in (self._watch_task, self._health_task):
                if task and not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            self._watch_task = self._health_task = None
            await self._kill()

            try:
                await self._spawn()
                await self._ping_check()
            except Exception as e:
                logger.error(f"[{self.manifest.name}] Spawn/ping échoué : {e}")
                continue

            self._state       = ProcessState.RUNNING
            self._started_at  = time.monotonic()
            self._watch_task  = asyncio.create_task(
                self._watch_loop(), name=f"watch-{self.manifest.name}"
            )
            hc = self.manifest.runtime.health_check
            if hc.enabled:
                self._health_task = asyncio.create_task(
                    self._health_loop(hc.interval_seconds, hc.timeout_seconds),
                    name=f"health-{self.manifest.name}",
                )
            logger.info(f"[{self.manifest.name}] ✅ Redémarré")
            return

        self._state = ProcessState.FAILED
        logger.error(f"[{self.manifest.name}] ❌ FAILED après {self._restarts} tentative(s)")

    async def stop(self) -> None:
        self._state = ProcessState.STOPPED
        for task in (self._watch_task, self._health_task):
            if task and not task.done():
                task.cancel()
        if self._channel:
            await self._channel.close()
        await self._kill()

    async def _kill(self) -> None:
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()
            except Exception:
                logger.exception(f"[{self.manifest.name}] _kill() erreur")

    def status(self) -> dict:
        return {
            "name":     self.manifest.name,
            "mode":     "sandboxed",
            "state":    self._state.value,
            "pid":      self._process.pid if self._process else None,
            "restarts": self._restarts,
            "uptime":   round(self.uptime, 1) if self.uptime else None,
            "disk":     self._disk.stats(),
        }
