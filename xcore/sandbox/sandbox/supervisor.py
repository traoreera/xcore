"""
──────────────────────
Superviseur du cycle de vie d'un plugin Sandboxed.
Intègre : mémoire (via worker), health check, env injection, disk watcher.
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

from .disk_watcher import DiskQuotaExceeded, DiskWatcher
from .ipc import IPCChannel, IPCProcessDead, IPCResponse

logger = logging.getLogger("plManager.supervisor")


class ProcessState(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    RESTARTING = auto()
    FAILED = auto()


@dataclass
class SupervisorConfig:
    timeout: float = 10.0
    max_restarts: int = 3
    restart_delay: float = 1.0
    startup_timeout: float = 5.0


class SandboxSupervisor:

    def __init__(self, manifest, config: SupervisorConfig | None = None) -> None:
        self.manifest = manifest
        self.config = config or SupervisorConfig()
        self._process: asyncio.subprocess.Process | None = None
        self._channel: IPCChannel | None = None
        self._state: ProcessState = ProcessState.STOPPED
        self._restarts: int = 0
        self._started_at: float | None = None
        self._watch_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None
        data_dir = manifest.plugin_dir / "data"
        self._disk = DiskWatcher(data_dir, manifest.resources.max_disk_mb)

    @property
    def state(self) -> ProcessState:
        return self._state

    @property
    def is_available(self) -> bool:
        return self._state == ProcessState.RUNNING

    @property
    def uptime(self) -> float | None:
        if self._started_at is None:
            return None
        return time.monotonic() - self._started_at

    async def start(self) -> None:
        if self._state == ProcessState.FAILED:
            raise RuntimeError(f"Plugin {self.manifest.name} en état FAILED.")
        if self._state == ProcessState.RUNNING:
            return
        self._state = ProcessState.STARTING
        logger.info(f"[{self.manifest.name}] Démarrage subprocess...")
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
        logger.info(
            f"[{self.manifest.name}] ✅ Subprocess démarré (PID={self._process.pid})"
        )

    async def _spawn(self) -> None:
        """
        Lance worker.py dans un subprocess isolé.

        IMPORTANT — Limite mémoire :
        On ne fait JAMAIS setrlimit() depuis ce process (uvicorn).
        Le setrlimit après create_subprocess_exec() s'appliquerait au
        process uvicorn lui-même → core dump immédiat.
        La limite est passée via _SANDBOX_MAX_MEM_MB et appliquée
        par le worker dans son propre process au démarrage.
        """
        worker = Path(__file__).parent / "worker.py"
        venv_python = self.manifest.plugin_dir / "venv" / "bin" / "python"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        sandbox_home = (self.manifest.plugin_dir / ".sandbox_home").resolve()
        sandbox_home.mkdir(parents=True, exist_ok=True)

        # Env minimal — pas d'héritage de l'env uvicorn pour éviter
        # la fuite de secrets (DB_PASSWORD, JWT_SECRET, etc.)
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
            python_exe,
            str(worker),
            str(self.manifest.plugin_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.manifest.plugin_dir),
            env=env,
        )
        self._channel = IPCChannel(
            self._process,
            timeout=self.manifest.resources.timeout_seconds,
        )
        logger.debug(
            f"[{self.manifest.name}] PID={self._process.pid} | "
            f"mem_limit={self.manifest.resources.max_memory_mb}MB"
        )

    async def _ping_check(self) -> None:
        hc_timeout = self.manifest.runtime.health_check.timeout_seconds
        timeout = max(hc_timeout, self.config.startup_timeout)
        try:
            resp = await asyncio.wait_for(
                self._channel.call("ping", {}), timeout=timeout
            )
            if not resp.success:
                raise RuntimeError(f"Ping échoué : {resp.data}")
        except asyncio.TimeoutError as e:
            await self._kill()
            raise RuntimeError(
                f"[{self.manifest.name}] Pas de réponse au ping dans {timeout}s"
            ) from e

    async def call(self, action: str, payload: dict) -> IPCResponse:
        if not self.is_available:
            raise RuntimeError(
                f"Plugin {self.manifest.name} non disponible ({self._state.name})"
            )
        try:
            self._disk.check(self.manifest.name)
        except DiskQuotaExceeded as e:
            return IPCResponse(
                success=False,
                data={"status": "error", "msg": str(e), "code": "disk_quota"},
            )
        try:
            return await self._channel.call(action, payload)
        except IPCProcessDead:
            logger.warning(f"[{self.manifest.name}] Process mort durant l'appel")
            await self._handle_crash()
            raise

    async def _health_loop(self, interval: float, timeout: float) -> None:
        await asyncio.sleep(interval)
        while self._state == ProcessState.RUNNING:
            try:
                resp = await asyncio.wait_for(
                    self._channel.call("ping", {}), timeout=timeout
                )
                if not resp.success:
                    logger.warning(
                        f"[{self.manifest.name}] Health dégradé: {resp.data}"
                    )
                else:
                    logger.debug(f"[{self.manifest.name}] Health OK")
            except asyncio.TimeoutError:
                logger.error(f"[{self.manifest.name}] Health timeout — restart...")
                await self._handle_crash()
                return
            except Exception as e:
                logger.error(f"[{self.manifest.name}] Health erreur: {e}")
                await self._handle_crash()
                return
            await asyncio.sleep(interval)

    async def _watch_loop(self) -> None:
        if self._process is None:
            return
        returncode = await self._process.wait()
        if self._state == ProcessState.STOPPED:
            return
        logger.warning(f"[{self.manifest.name}] Subprocess terminé (code={returncode})")
        if self._process.stderr:
            with contextlib.suppress(Exception):
                err = await asyncio.wait_for(
                    self._process.stderr.read(2048), timeout=1.0
                )
                if err:
                    logger.error(
                        f"[{self.manifest.name}] stderr: "
                        f"{err.decode('utf-8', errors='replace').strip()}"
                    )
        await self._handle_crash()

    async def _handle_crash(self) -> None:
        self._restarts += 1
        if self._restarts > self.config.max_restarts:
            self._state = ProcessState.FAILED
            logger.error(
                f"[{self.manifest.name}] ❌ FAILED après {self._restarts-1} crashs"
            )
            return
        self._state = ProcessState.RESTARTING
        logger.info(
            f"[{self.manifest.name}] Restart {self._restarts}/{self.config.max_restarts}..."
        )
        await asyncio.sleep(self.config.restart_delay)
        try:
            await self.start()
        except Exception as e:
            logger.error(f"[{self.manifest.name}] Échec restart: {e}")
            await self._handle_crash()

    async def stop(self) -> None:
        self._state = ProcessState.STOPPED
        for task in (self._watch_task, self._health_task):
            if task and not task.done():
                task.cancel()
        if self._channel:
            await self._channel.close()
        await self._kill()
        logger.info(f"[{self.manifest.name}] Subprocess arrêté")

    async def _kill(self) -> None:
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()
            except Exception:
                logger.exception(
                    f"[{self.manifest.name}] Erreur inattendue pendant _kill()"
                )

    def status(self) -> dict:
        return {
            "name": self.manifest.name,
            "mode": "sandboxed",
            "state": self._state.name,
            "pid": self._process.pid if self._process else None,
            "restarts": self._restarts,
            "uptime": round(self.uptime, 1) if self.uptime else None,
            "disk": self._disk.stats(),
            "limits": {
                "timeout_s": self.manifest.resources.timeout_seconds,
                "max_memory_mb": self.manifest.resources.max_memory_mb,
                "max_disk_mb": self.manifest.resources.max_disk_mb,
                "rate_limit": {
                    "calls": self.manifest.resources.rate_limit.calls,
                    "period_seconds": self.manifest.resources.rate_limit.period_seconds,
                },
            },
        }
