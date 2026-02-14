"""
plugin_manager.py
──────────────────
Orchestrateur central du système de plugins.
Point d'entrée unique pour le Core FastAPI.

Usage:
    manager = PluginManager(plugins_dir="plugins", secret_key=b"...")
    await manager.load_all()
    result = await manager.call("mon_plugin", "ping", {})
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .contracts.plugin_manifest import (
    ExecutionMode, ManifestError, PluginManifest,
    check_framework_compatibility, load_manifest,
)
from .contracts.base_plugin import error as plugin_error
from .trusted.runner import TrustedRunner, TrustedLoadError
from .trusted.signer import SignatureError, verify_plugin
from .sandbox.scanner import ASTScanner
from .sandbox.supervisor import SandboxSupervisor, SupervisorConfig
from .sandbox.rate_limiter import RateLimiterRegistry, RateLimitExceeded

logger = logging.getLogger("plManager")

CORE_VERSION = "1.0.0"


class PluginNotFound(Exception):
    pass


class PluginManager:

    def __init__(
        self,
        plugins_dir:    str | Path,
        secret_key:     bytes,
        services:       dict[str, Any] | None = None,
        sandbox_config: SupervisorConfig | None = None,
        strict_trusted: bool = True,
    ) -> None:
        self.plugins_dir    = Path(plugins_dir)
        self._secret_key    = secret_key
        self._services      = services or {}
        self._sandbox_cfg   = sandbox_config or SupervisorConfig()
        self._strict_trusted = strict_trusted

        self._trusted:   dict[str, TrustedRunner]     = {}
        self._sandboxed: dict[str, SandboxSupervisor] = {}
        self._scanner    = ASTScanner()
        self._rate        = RateLimiterRegistry()

    # ──────────────────────────────────────────
    # Chargement
    # ──────────────────────────────────────────

    async def load_all(self) -> dict[str, list[str]]:
        loaded, failed, skipped = [], [], []

        for plugin_dir in sorted(self.plugins_dir.iterdir()):
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                continue
            try:
                manifest = load_manifest(plugin_dir)
            except ManifestError as e:
                logger.warning(f"[{plugin_dir.name}] Manifeste invalide : {e}")
                skipped.append(plugin_dir.name)
                continue

            try:
                await self._activate(manifest)
                loaded.append(manifest.name)
            except Exception as e:
                logger.error(f"[{manifest.name}] Échec activation : {e}")
                failed.append(manifest.name)

        logger.info(
            f"Plugins — chargés: {len(loaded)}, "
            f"échecs: {len(failed)}, ignorés: {len(skipped)}"
        )
        return {"loaded": loaded, "failed": failed, "skipped": skipped}

    async def _activate(self, manifest: PluginManifest) -> None:
        if not check_framework_compatibility(manifest, CORE_VERSION):
            raise ValueError(
                f"Incompatibilité framework : plugin requiert "
                f"{manifest.framework_version}, core={CORE_VERSION}"
            )

        if manifest.execution_mode == ExecutionMode.LEGACY:
            logger.warning(
                f"[{manifest.name}] Mode LEGACY — déclarez "
                "'trusted' ou 'sandboxed' dans plugin.yaml."
            )

        # Enregistrement rate limiter
        self._rate.register(manifest.name, manifest.resources.rate_limit)

        if manifest.execution_mode in (ExecutionMode.TRUSTED, ExecutionMode.LEGACY):
            await self._activate_trusted(manifest)
        elif manifest.execution_mode == ExecutionMode.SANDBOXED:
            await self._activate_sandboxed(manifest)

    async def _activate_trusted(self, manifest: PluginManifest) -> None:
        if manifest.execution_mode == ExecutionMode.TRUSTED or self._strict_trusted:
            try:
                verify_plugin(manifest, self._secret_key)
            except SignatureError as e:
                raise TrustedLoadError(str(e))

        runner = TrustedRunner(manifest, services=self._services)
        await runner.load()
        self._trusted[manifest.name] = runner
        logger.info(
            f"[{manifest.name}] ✅ TRUSTED | "
            f"timeout={manifest.resources.timeout_seconds}s | "
            f"rate={manifest.resources.rate_limit.calls}/"
            f"{manifest.resources.rate_limit.period_seconds}s"
        )

    async def _activate_sandboxed(self, manifest: PluginManifest) -> None:
        scan = self._scanner.scan_plugin(
            manifest.plugin_dir,
            whitelist=manifest.allowed_imports,
        )
        if not scan.passed:
            raise ValueError(f"[{manifest.name}] Scan statique échoué :\n{scan}")
        for w in scan.warnings:
            logger.warning(f"[{manifest.name}] ⚠️  {w}")

        supervisor = SandboxSupervisor(manifest, config=self._sandbox_cfg)
        await supervisor.start()
        self._sandboxed[manifest.name] = supervisor
        logger.info(
            f"[{manifest.name}] ✅ SANDBOXED | "
            f"mem={manifest.resources.max_memory_mb}MB | "
            f"disk={manifest.resources.max_disk_mb}MB | "
            f"timeout={manifest.resources.timeout_seconds}s | "
            f"rate={manifest.resources.rate_limit.calls}/"
            f"{manifest.resources.rate_limit.period_seconds}s | "
            f"health_check={'on' if manifest.runtime.health_check.enabled else 'off'}"
        )

    # ──────────────────────────────────────────
    # Appel public avec retry + rate limit
    # ──────────────────────────────────────────

    async def call(
        self,
        plugin_name: str,
        action:      str,
        payload:     dict,
    ) -> dict:
        """
        Point d'entrée unique.
        Applique : rate limiting → retry/backoff → routing Trusted/Sandbox.
        """
        # 1. Rate limiting
        try:
            await self._rate.check(plugin_name)
        except RateLimitExceeded as e:
            return plugin_error(str(e), code="rate_limit_exceeded")

        # 2. Routing avec retry
        if plugin_name in self._trusted:
            return await self._call_with_retry(
                plugin_name,
                self._trusted[plugin_name].call,
                action, payload,
            )

        if plugin_name in self._sandboxed:
            supervisor = self._sandboxed[plugin_name]
            if not supervisor.is_available:
                return plugin_error(
                    f"Plugin '{plugin_name}' non disponible "
                    f"(état: {supervisor.state.name})",
                    code="unavailable",
                )
            async def _sandbox_call(a, p):
                resp = await supervisor.call(a, p)
                return resp.data
            return await self._call_with_retry(
                plugin_name, _sandbox_call, action, payload,
            )

        return plugin_error(f"Plugin '{plugin_name}' introuvable", code="not_found")

    async def _call_with_retry(
        self,
        plugin_name: str,
        fn,
        action: str,
        payload: dict,
    ) -> dict:
        """Wrapper retry avec backoff exponentiel."""
        manifest = self._get_manifest(plugin_name)
        if manifest is None:
            return await fn(action, payload)

        retry_cfg   = manifest.runtime.retry
        last_error  = None
        backoff     = retry_cfg.backoff_seconds

        for attempt in range(1, retry_cfg.max_attempts + 1):
            try:
                return await fn(action, payload)
            except Exception as e:
                last_error = e
                if attempt < retry_cfg.max_attempts:
                    logger.warning(
                        f"[{plugin_name}] Tentative {attempt}/"
                        f"{retry_cfg.max_attempts} échouée : {e}. "
                        f"Retry dans {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2  # backoff exponentiel

        logger.error(
            f"[{plugin_name}] Toutes les tentatives échouées : {last_error}"
        )
        return plugin_error(str(last_error), code="all_retries_failed")

    def _get_manifest(self, plugin_name: str) -> PluginManifest | None:
        if plugin_name in self._trusted:
            return self._trusted[plugin_name].manifest
        if plugin_name in self._sandboxed:
            return self._sandboxed[plugin_name].manifest
        return None

    # ──────────────────────────────────────────
    # Gestion du cycle de vie
    # ──────────────────────────────────────────

    async def reload(self, plugin_name: str) -> None:
        if plugin_name in self._trusted:
            await self._trusted[plugin_name].reload()
        elif plugin_name in self._sandboxed:
            manifest = self._sandboxed[plugin_name].manifest
            await self._sandboxed[plugin_name].stop()
            del self._sandboxed[plugin_name]
            await self._activate_sandboxed(manifest)
        else:
            raise PluginNotFound(f"Plugin '{plugin_name}' non chargé")

    async def shutdown(self) -> None:
        logger.info("Arrêt du PluginManager...")
        for name, runner in self._trusted.items():
            try:
                await runner.unload()
            except Exception as e:
                logger.error(f"[{name}] Erreur déchargement : {e}")
        for name, sup in self._sandboxed.items():
            try:
                await sup.stop()
            except Exception as e:
                logger.error(f"[{name}] Erreur arrêt : {e}")
        self._trusted.clear()
        self._sandboxed.clear()
        logger.info("PluginManager arrêté.")

    # ──────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────

    def status(self) -> dict:
        return {
            "trusted":   [r.status() for r in self._trusted.values()],
            "sandboxed": [s.status() for s in self._sandboxed.values()],
        }