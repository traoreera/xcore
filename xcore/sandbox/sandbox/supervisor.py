"""
sandbox/supervisor.py
──────────────────────
Superviseur du cycle de vie d'un plugin Sandboxed.
Intègre : mémoire, health check, env injection, disk watcher.
"""

from __future__ import annotations

import asyncio
import logging
import resource as _resource
import sys
import time
from pathlib import Path

from .disk_watcher import DiskWatcher, DiskQuotaExceeded
from .ipc import IPCChannel, IPCError, IPCProcessDead, IPCResponse
from ..contracts.plugin_manifest import PluginManifest

logger = logging.getLogger("plManager.supervisor")

# ── Import conditionnel ProcessState (défini ici si absent du manifest) ──
try:
    from ..contracts.plugin_manifest import ProcessState
except ImportError:
    from enum import Enum, auto
    class ProcessState(Enum):
        STOPPED    = auto()
        STARTING   = auto()
        RUNNING    = auto()
        RESTARTING = auto()
        FAILED     = auto()


# ══════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════

from dataclasses import dataclass

@dataclass
class SupervisorConfig:
    timeout:         float = 10.0
    max_restarts:    int   = 3
    restart_delay:   float = 1.0
    startup_timeout: float = 5.0


# ══════════════════════════════════════════════
# Supervisor
# ══════════════════════════════════════════════

class SandboxSupervisor:

    def __init__(
        self,
        manifest: PluginManifest,
        config:   SupervisorConfig | None = None,
    ) -> None:
        self.manifest  = manifest
        self.config    = config or SupervisorConfig()

        self._process:    asyncio.subprocess.Process | None = None
        self._channel:    IPCChannel | None                 = None
        self._state:      ProcessState                      = ProcessState.STOPPED
        self._restarts:   int                               = 0
        self._started_at: float | None                      = None
        self._watch_task:  asyncio.Task | None              = None
        self._health_task: asyncio.Task | None              = None

        # Disk watcher
        data_dir = manifest.plugin_dir / "data"
        self._disk = DiskWatcher(data_dir, manifest.resources.max_disk_mb)

    # ──────────────────────────────────────────
    # Propriétés
    # ──────────────────────────────────────────

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

    # ──────────────────────────────────────────
    # Démarrage
    # ──────────────────────────────────────────

    async def start(self) -> None:
        if self._state == ProcessState.FAILED:
            raise RuntimeError(
                f"Plugin {self.manifest.name} en état FAILED. "
                "Rechargement manuel requis."
            )
        if self._state == ProcessState.RUNNING:
            return

        self._state = ProcessState.STARTING
        logger.info(f"[{self.manifest.name}] Démarrage subprocess...")

        await self._spawn()
        await self._ping_check()

        self._state      = ProcessState.RUNNING
        self._started_at = time.monotonic()
        self._restarts   = 0

        # Tâche de surveillance crash
        self._watch_task = asyncio.create_task(
            self._watch_loop(), name=f"watch-{self.manifest.name}"
        )

        # Tâche health check périodique
        hc = self.manifest.runtime.health_check
        if hc.enabled:
            self._health_task = asyncio.create_task(
                self._health_loop(hc.interval_seconds, hc.timeout_seconds),
                name=f"health-{self.manifest.name}",
            )

        logger.info(f"[{self.manifest.name}] ✅ Subprocess démarré (PID={self._process.pid})")

    async def _spawn(self) -> None:
        """Lance le subprocess avec toutes les configs prod."""
        worker     = Path(__file__).parent / "worker.py"
        venv_python = self.manifest.plugin_dir / "venv" / "bin" / "python"
        python_exe  = str(venv_python) if venv_python.exists() else sys.executable

        # ── Variables d'environnement injectées ────────────────
        import os
        env = {**os.environ}          # hérite de l'env courant
        env.update(self.manifest.env) # surcharge avec les vars du manifest

        # ── Limite mémoire via preexec_fn (Linux uniquement) ───
        preexec = None
        max_mem = self.manifest.resources.max_memory_mb
        if max_mem > 0 and sys.platform != "win32":
            limit_bytes = max_mem * 1024 * 1024
            def _set_mem_limit():
                try:
                    _resource.setrlimit(
                        _resource.RLIMIT_AS,
                        (limit_bytes, limit_bytes)
                    )
                except Exception as e:
                    logger.warning(f"Impossible de limiter lamoire: {e}") # non-fatal si cgroups non disponibles
            preexec = _set_mem_limit

        kwargs = dict(
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.manifest.plugin_dir),
            env=env,
        )

        self._process = await asyncio.create_subprocess_exec(
            python_exe,
            str(worker),
            str(self.manifest.plugin_dir),
            **kwargs,
        )

        # Applique la limite mémoire si sur Linux
        if preexec and self._process.pid:
            try:
                preexec()
            except Exception as e :
                logger.warning(
                    f"Impossible de limiter l'usage de lamoire: {e}"
                )

        self._channel = IPCChannel(
            self._process,
            timeout=self.manifest.resources.timeout_seconds,
        )

        logger.debug(
            f"[{self.manifest.name}] PID={self._process.pid} | "
            f"mem_limit={max_mem}MB | "
            f"env_vars={list(self.manifest.env.keys())}"
        )

    async def _ping_check(self) -> None:
        hc_timeout = self.manifest.runtime.health_check.timeout_seconds
        timeout    = max(hc_timeout, self.config.startup_timeout)
        try:
            resp = await asyncio.wait_for(
                self._channel.call("ping", {}),
                timeout=timeout,
            )
            if not resp.success:
                raise RuntimeError(f"Ping échoué : {resp.data}")
        except asyncio.TimeoutError as e :
            await self._kill()
            raise RuntimeError(
                f"[{self.manifest.name}] Pas de réponse au ping dans {timeout}s"
            ) from e

    # ──────────────────────────────────────────
    # Appel IPC
    # ──────────────────────────────────────────

    async def call(self, action: str, payload: dict) -> IPCResponse:
        if not self.is_available:
            raise RuntimeError(
                f"Plugin {self.manifest.name} non disponible "
                f"(état: {self._state.name})"
            )

        # Vérification quota disque avant chaque appel
        try:
            self._disk.check(self.manifest.name)
        except DiskQuotaExceeded as e:
            from .ipc import IPCResponse
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

    # ──────────────────────────────────────────
    # Health check périodique
    # ──────────────────────────────────────────

    async def _health_loop(self, interval: float, timeout: float) -> None:
        """Envoie un ping périodique pour détecter les zombies silencieux."""
        await asyncio.sleep(interval)  # premier check après le délai
        while self._state == ProcessState.RUNNING:
            try:
                resp = await asyncio.wait_for(
                    self._channel.call("ping", {}),
                    timeout=timeout,
                )
                if not resp.success:
                    logger.warning(
                        f"[{self.manifest.name}] Health check dégradé : {resp.data}"
                    )
                else:
                    logger.debug(f"[{self.manifest.name}] Health check OK")
            except asyncio.TimeoutError:
                logger.error(
                    f"[{self.manifest.name}] Health check timeout ({timeout}s) — "
                    "redémarrage..."
                )
                await self._handle_crash()
                return
            except Exception as e:
                logger.error(f"[{self.manifest.name}] Health check erreur : {e}")
                await self._handle_crash()
                return

            await asyncio.sleep(interval)

    # ──────────────────────────────────────────
    # Surveillance crash + restart
    # ──────────────────────────────────────────

    async def _watch_loop(self) -> None:
        if self._process is None:
            return
        returncode = await self._process.wait()
        if self._state == ProcessState.STOPPED:
            return
        logger.warning(
            f"[{self.manifest.name}] Subprocess terminé (code={returncode})"
        )
        # Log stderr pour le diagnostic
        if self._process.stderr:
            try:
                err = await asyncio.wait_for(
                    self._process.stderr.read(2048), timeout=1.0
                )
                if err:
                    logger.error(
                        f"[{self.manifest.name}] stderr: "
                        f"{err.decode('utf-8', errors='replace').strip()}"
                    )
            except Exception as e :
                logger.warning(
                    f"[{self.manifest.name}] Erreur lecture stderr : {e}"
                )

        await self._handle_crash()

    async def _handle_crash(self) -> None:
        self._restarts += 1
        if self._restarts > self.config.max_restarts:
            self._state = ProcessState.FAILED
            logger.error(
                f"[{self.manifest.name}] ❌ FAILED après "
                f"{self._restarts - 1} crashs"
            )
            return

        self._state = ProcessState.RESTARTING
        logger.info(
            f"[{self.manifest.name}] Restart {self._restarts}/"
            f"{self.config.max_restarts} dans {self.config.restart_delay}s..."
        )
        await asyncio.sleep(self.config.restart_delay)

        try:
            await self.start()
        except Exception as e:
            logger.error(f"[{self.manifest.name}] Échec restart : {e}")
            await self._handle_crash()

    # ──────────────────────────────────────────
    # Arrêt
    # ──────────────────────────────────────────

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
                pass

    # ──────────────────────────────────────────
    # Status complet
    # ──────────────────────────────────────────

    def status(self) -> dict:
        return {
            "name":     self.manifest.name,
            "mode":     "sandboxed",
            "state":    self._state.name,
            "pid":      self._process.pid if self._process else None,
            "restarts": self._restarts,
            "uptime":   round(self.uptime, 1) if self.uptime else None,
            "disk":     self._disk.stats(),
            "limits": {
                "timeout_s":    self.manifest.resources.timeout_seconds,
                "max_memory_mb": self.manifest.resources.max_memory_mb,
                "max_disk_mb":  self.manifest.resources.max_disk_mb,
                "rate_limit": {
                    "calls":          self.manifest.resources.rate_limit.calls,
                    "period_seconds": self.manifest.resources.rate_limit.period_seconds,
                },
            },
        }