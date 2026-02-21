"""
plugin_manager.py — PATCH FINAL
═════════════════════════════════
Adapté au code réel après lecture de runner.py.

Le vrai mécanisme de partage des services dans xcore :
  - PluginManager._services est un dict partagé (passé par référence)
  - TrustedRunner reçoit CE MÊME dict à l'init
  - Plugin hérite de TrustedBase → self._services pointe sur CE MÊME dict
  - on_load() peut donc écrire self._services["core"] = CoreService(...)
    et PluginManager._services["core"] est automatiquement mis à jour

MAIS : si Plugin() ne prend pas `services` en __init__ et n'hérite pas de
TrustedBase, l'injection échoue silencieusement.

Corrections dans runner.py (fichier séparé) :
  1. Injection forcée de _services même si __init__ ne l'accepte pas
  2. mems() appelé après on_load() pour synchroniser

Correction dans manager.py (ce fichier) :
  _flush_services() appelle runner.mems() au lieu de register_services()
  → compatible avec l'architecture existante, aucun changement dans les plugins
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

from .contracts.base_plugin import error as plugin_error
from .contracts.plugin_manifest import (
    ExecutionMode,
    ManifestError,
    PluginManifest,
    check_framework_compatibility,
    load_manifest,
)
from .sandbox.rate_limiter import RateLimiterRegistry, RateLimitExceeded
from .sandbox.scanner import ASTScanner
from .sandbox.supervisor import SandboxSupervisor, SupervisorConfig
from .trusted.runner import TrustedLoadError, TrustedRunner
from .trusted.signer import SignatureError, verify_plugin

logger = logging.getLogger("plManager")

CORE_VERSION = "1.0.0"


class PluginNotFound(Exception):
    pass


class PluginManager:
    def __init__(
        self,
        plugins_dir: str | Path,
        secret_key: bytes,
        services: dict[str, Any] | None = None,
        sandbox_config: SupervisorConfig | None = None,
        strict_trusted: bool = True,
        app: "FastAPI | None" = None,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self._secret_key = secret_key
        self._services = services if services is not None else {}
        self._sandbox_cfg = sandbox_config or SupervisorConfig()
        self._strict_trusted = strict_trusted
        self._app = app

        self._trusted: dict[str, TrustedRunner] = {}
        self._sandboxed: dict[str, SandboxSupervisor] = {}
        self._scanner = ASTScanner()
        self._rate = RateLimiterRegistry()

    # ─────────────────────────────────────────────────────────────────────────
    # Tri topologique (inchangé)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _topo_sort(manifests: list[PluginManifest]) -> list[PluginManifest]:
        from collections import deque

        by_name = {m.name: m for m in manifests}
        in_degree = {m.name: 0 for m in manifests}
        dependents: dict[str, list[str]] = {m.name: [] for m in manifests}

        for m in manifests:
            for dep in m.requires:
                if dep not in by_name:
                    raise ValueError(
                        f"[{m.name}] Dépendance introuvable : '{dep}'.\n"
                        f"  Plugins disponibles : {sorted(by_name.keys())}"
                    )
                dependents[dep].append(m.name)
                in_degree[m.name] += 1

        queue: deque[str] = deque(
            sorted(name for name, deg in in_degree.items() if deg == 0)
        )
        result: list[PluginManifest] = []

        while queue:
            name = queue.popleft()
            result.append(by_name[name])
            for dep_name in sorted(dependents[name]):
                in_degree[dep_name] -= 1
                if in_degree[dep_name] == 0:
                    queue.append(dep_name)

        if len(result) != len(manifests):
            remaining = [
                m.name for m in manifests if m.name not in {s.name for s in result}
            ]
            raise ValueError(f"Dépendances circulaires : {remaining}")

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # ★ CORRIGÉ — _flush_services utilise runner.mems()
    # ─────────────────────────────────────────────────────────────────────────

    async def _flush_services(self, plugin_names: list[str]) -> None:
        """
        Synchronise les services exposés par chaque plugin de la vague
        vers self._services (container partagé du PluginManager).

        Utilise runner.mems() — le mécanisme natif de xcore —
        plutôt qu'une méthode register_services() inexistante.

        Sans ce flush :
          vague 1 → erp_core.on_load() → self._services["core"] = CoreService
                    Mais si _services du plugin != _services du manager → perdu
          vague 2 → erp_auth → services["core"] introuvable 💥

        Avec ce flush :
          vague 1 → erp_core chargé + mems() appelé
                    → manager._services["core"] = CoreService  ✓
          vague 2 → erp_auth → services["core"] disponible  ✓
        """
        for name in plugin_names:
            if name not in self._trusted:
                continue

            runner = self._trusted[name]

            # runner.mems() synchronise instance._services → self._services
            # (le container partagé reçoit les nouveaux services du plugin)
            updated = runner.mems()

            # Log des services disponibles après flush
            logger.info(f"[{name}] 📦 Services disponibles : {sorted(updated.keys())}")

    # ─────────────────────────────────────────────────────────────────────────
    # load_all avec flush entre chaque vague
    # ─────────────────────────────────────────────────────────────────────────

    async def load_all(self) -> dict[str, list[str]]:
        """
        Charge tous les plugins dans l'ordre topologique.

        Flux par vague :
          1. gather() — active les plugins en parallèle
          2. _flush_services() — runner.mems() propage leurs services
          3. Vague suivante — services de la vague précédente disponibles ✓
        """
        loaded, failed, skipped = [], [], []
        manifests: list[PluginManifest] = []

        for plugin_dir in sorted(self.plugins_dir.iterdir()):
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                continue
            try:
                manifests.append(load_manifest(plugin_dir))
            except ManifestError as e:
                logger.warning(f"[{plugin_dir.name}] Manifeste invalide : {e}")
                skipped.append(plugin_dir.name)

        if not manifests:
            return {"loaded": [], "failed": [], "skipped": skipped}

        try:
            ordered = self._topo_sort(manifests)
        except ValueError as e:
            logger.error(f"Erreur dépendances : {e}")
            return {
                "loaded": [],
                "failed": [m.name for m in manifests],
                "skipped": skipped,
            }

        resolved: set[str] = set()

        async def _try_activate(manifest: PluginManifest) -> tuple[str, bool]:
            try:
                await self._activate(manifest)
                self._attach_routes(manifest)
                return manifest.name, True
            except Exception as e:
                logger.error(f"[{manifest.name}] Échec activation : {e}")
                return manifest.name, False

        remaining = list(ordered)

        while remaining:
            wave = [m for m in remaining if all(dep in resolved for dep in m.requires)]
            if not wave:
                stuck = [m.name for m in remaining]
                logger.error(f"Chargement bloqué : {stuck}")
                failed.extend(stuck)
                break

            logger.info(f"⚡ Vague : [{', '.join(m.name for m in wave)}]")

            results = await asyncio.gather(*[_try_activate(m) for m in wave])

            wave_loaded = []
            for name, ok in results:
                if ok:
                    loaded.append(name)
                    resolved.add(name)
                    wave_loaded.append(name)
                else:
                    failed.append(name)
                    cascade = [
                        m.name
                        for m in remaining
                        if name in m.requires and m.name not in failed
                    ]
                    if cascade:
                        logger.error(f"[{name}] Cascade : {cascade}")
                        failed.extend(cascade)
                        resolved.update(cascade)

            # ★ Flush AVANT la prochaine vague
            if wave_loaded:
                await self._flush_services(wave_loaded)

            remaining = [
                m for m in remaining if m.name not in resolved and m.name not in failed
            ]

        logger.info(
            f"Plugins — chargés: {len(loaded)}, "
            f"échecs: {len(failed)}, ignorés: {len(skipped)}"
        )
        return {"loaded": loaded, "failed": failed, "skipped": skipped}

    # ─────────────────────────────────────────────────────────────────────────
    # load() individuel avec flush après chaque dépendance
    # ─────────────────────────────────────────────────────────────────────────

    async def load(self, plugin_name: str) -> None:
        plugin_dir = self.plugins_dir / plugin_name
        if not plugin_dir.is_dir():
            raise PluginNotFound(f"Dossier '{plugin_dir}' introuvable")

        manifest = load_manifest(plugin_dir)
        already_loaded = set(self._trusted) | set(self._sandboxed)

        for dep_name in manifest.requires:
            if dep_name in already_loaded:
                continue
            logger.info(f"[{plugin_name}] Dépendance '{dep_name}' → chargement...")
            await self.load(dep_name)  # récursif — flush inclus

        await self._activate(manifest)
        self._attach_routes(manifest)
        await self._flush_services([plugin_name])
        logger.info(f"[{plugin_name}] ✅ Chargé")

    # ─────────────────────────────────────────────────────────────────────────
    # reload() avec flush après
    # ─────────────────────────────────────────────────────────────────────────

    async def reload(self, plugin_name: str) -> None:
        if plugin_name not in self._trusted and plugin_name not in self._sandboxed:
            await self.load(plugin_name)
            return

        plugin_dir = self.plugins_dir / plugin_name
        manifest = load_manifest(plugin_dir)
        already_loaded = set(self._trusted) | set(self._sandboxed)

        for dep_name in manifest.requires:
            if dep_name not in already_loaded:
                logger.warning(
                    f"[{plugin_name}] '{dep_name}' manquante → chargement..."
                )
                await self.load(dep_name)

        if plugin_name in self._trusted:
            await self._trusted[plugin_name].reload()
            manifest = self._trusted[plugin_name].manifest
            self._rate.register(plugin_name, manifest.resources.rate_limit)
            self._attach_routes(manifest)
        elif plugin_name in self._sandboxed:
            manifest = self._sandboxed[plugin_name].manifest
            await self._sandboxed[plugin_name].stop()
            del self._sandboxed[plugin_name]
            await self._activate_sandboxed(manifest)
            self._rate.register(plugin_name, manifest.resources.rate_limit)

        await self._flush_services([plugin_name])
        logger.info(f"[{plugin_name}] 🔄 Rechargé")

    # ─────────────────────────────────────────────────────────────────────────
    # Reste inchangé
    # ─────────────────────────────────────────────────────────────────────────

    def _attach_routes(self, manifest: PluginManifest) -> None:
        if self._app is None or manifest.name not in self._trusted:
            return
        runner = self._trusted[manifest.name]
        instance = runner._instance
        module = runner._module
        api_router = getattr(instance, "router", None) or getattr(
            module, "router", None
        )
        if api_router is None:
            return
        try:
            self._app.include_router(api_router)
            self._app.openapi_schema = None
            logger.info(f"[{manifest.name}] 🔗 Routes attachées")
        except Exception as e:
            logger.error(f"[{manifest.name}] Erreur include_router : {e}")

    async def _activate(self, manifest: PluginManifest) -> None:
        if not check_framework_compatibility(manifest, CORE_VERSION):
            raise ValueError(
                f"Incompatibilité framework : plugin requiert "
                f"{manifest.framework_version}, core={CORE_VERSION}"
            )
        if manifest.execution_mode == ExecutionMode.LEGACY:
            logger.warning(
                f"[{manifest.name}] Mode LEGACY — utilisez 'trusted' ou 'sandboxed'."
            )
        self._rate.register(manifest.name, manifest.resources.rate_limit)
        if manifest.execution_mode in (ExecutionMode.TRUSTED, ExecutionMode.LEGACY):
            await self._activate_trusted(manifest)
        elif manifest.execution_mode == ExecutionMode.SANDBOXED:
            await self._activate_sandboxed(manifest)

    async def _activate_trusted(self, manifest: PluginManifest) -> None:
        if manifest.execution_mode == ExecutionMode.TRUSTED or (
            manifest.execution_mode == ExecutionMode.LEGACY and self._strict_trusted
        ):
            try:
                verify_plugin(manifest, self._secret_key)
            except SignatureError as e:
                raise TrustedLoadError(str(e))

        scan = self._scanner.scan_plugin(
            manifest.plugin_dir, whitelist=manifest.allowed_imports
        )
        if not scan.passed:
            logger.warning(f"[{manifest.name}] ⚠️  Scan AST (non bloquant) :\n{scan}")
        for w in scan.warnings:
            logger.debug(f"[{manifest.name}] AST: {w}")

        runner = TrustedRunner(manifest, services=self._services)
        await runner.load()
        self._trusted[manifest.name] = runner
        logger.info(
            f"[{manifest.name}] ✅ TRUSTED | "
            f"timeout={manifest.resources.timeout_seconds}s"
        )

    async def _activate_sandboxed(self, manifest: PluginManifest) -> None:
        scan = self._scanner.scan_plugin(
            manifest.plugin_dir, whitelist=manifest.allowed_imports
        )
        if not scan.passed:
            raise ValueError(f"[{manifest.name}] Scan échoué :\n{scan}")
        for w in scan.warnings:
            logger.warning(f"[{manifest.name}] ⚠️  {w}")
        supervisor = SandboxSupervisor(manifest, config=self._sandbox_cfg)
        await supervisor.start()
        self._sandboxed[manifest.name] = supervisor
        logger.info(f"[{manifest.name}] ✅ SANDBOXED")

    async def call(self, plugin_name: str, action: str, payload: dict) -> dict:
        try:
            await self._rate.check(plugin_name)
        except RateLimitExceeded as e:
            return plugin_error(str(e), code="rate_limit_exceeded")

        if plugin_name in self._trusted:
            return await self._call_with_retry(
                plugin_name, self._trusted[plugin_name].call, action, payload
            )
        if plugin_name in self._sandboxed:
            supervisor = self._sandboxed[plugin_name]
            if not supervisor.is_available:
                return plugin_error(
                    f"Plugin '{plugin_name}' non disponible ({supervisor.state.name})",
                    code="unavailable",
                )

            async def _sandbox_call(a, p):
                return (await supervisor.call(a, p)).data

            return await self._call_with_retry(
                plugin_name, _sandbox_call, action, payload
            )

        return plugin_error(f"Plugin '{plugin_name}' introuvable", code="not_found")

    async def _call_with_retry(self, plugin_name, fn, action, payload) -> dict:
        manifest = self._get_manifest(plugin_name)
        if manifest is None:
            return await fn(action, payload)
        retry_cfg = manifest.runtime.retry
        last_error = None
        backoff = retry_cfg.backoff_seconds
        for attempt in range(1, retry_cfg.max_attempts + 1):
            try:
                return await fn(action, payload)
            except Exception as e:
                last_error = e
                if attempt < retry_cfg.max_attempts:
                    logger.warning(
                        f"[{plugin_name}] Tentative {attempt} échouée. "
                        f"Retry dans {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
        logger.error(f"[{plugin_name}] Toutes les tentatives échouées : {last_error}")
        return plugin_error(str(last_error), code="all_retries_failed")

    def _get_manifest(self, plugin_name: str) -> PluginManifest | None:
        if plugin_name in self._trusted:
            return self._trusted[plugin_name].manifest
        if plugin_name in self._sandboxed:
            return self._sandboxed[plugin_name].manifest
        return None

    async def unload(self, plugin_name: str) -> None:
        if plugin_name in self._trusted:
            await self._trusted[plugin_name].unload()
            del self._trusted[plugin_name]
            self._rate._limiters.pop(plugin_name, None)
        elif plugin_name in self._sandboxed:
            await self._sandboxed[plugin_name].stop()
            del self._sandboxed[plugin_name]
            self._rate._limiters.pop(plugin_name, None)
        else:
            raise PluginNotFound(f"Plugin '{plugin_name}' non chargé")

    async def shutdown(self, timeout: float = 10.0) -> None:
        logger.info(f"Arrêt PluginManager (timeout={timeout}s)...")

        async def _safe(coro, name):
            try:
                await asyncio.wait_for(coro, timeout=timeout)
            except Exception as e:
                logger.error(f"[{name}] Erreur arrêt : {e}")

        await asyncio.gather(
            *[_safe(r.unload(), n) for n, r in self._trusted.items()],
            *[_safe(s.stop(), n) for n, s in self._sandboxed.items()],
        )
        self._trusted.clear()
        self._sandboxed.clear()
        logger.info("PluginManager arrêté.")

    def status(self) -> dict:
        return {
            "trusted": [r.status() for r in self._trusted.values()],
            "sandboxed": [s.status() for s in self._sandboxed.values()],
        }
