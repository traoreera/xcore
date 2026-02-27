"""
loader.py — Découverte et chargement ordonné des plugins.

Responsabilités :
  - Scanner le dossier plugins/
  - Parser les manifestes (PluginManifest)
  - Tri topologique (dépendances via `requires`)
  - Déléguer à LifecycleManager (trusted) ou SandboxProcessManager (sandboxed)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import PluginConfig

from ...kernel.security.validation import ManifestValidator
from ..sandbox.process_manager import SandboxProcessManager
from .lifecycle import LifecycleManager, LoadError
from .state_machine import PluginState

logger = logging.getLogger("xcore.runtime.loader")


class PluginLoader:
    """
    Découvre, ordonne et charge tous les plugins d'un répertoire.

    Usage:
        loader = PluginLoader(config, services=shared_dict)
        report = await loader.load_all()
        # report = {"loaded": [...], "failed": [...], "skipped": [...]}

        # Chargement individuel
        await loader.load("my_plugin")

        # Accès
        lm = loader.get("my_plugin")      # LifecycleManager ou SandboxProcessManager
        result = await lm.call("ping", {})
    """

    def __init__(
        self,
        config: "PluginConfig",
        services: dict[str, Any],
        events=None,
        hooks=None,
    ) -> None:
        self._config = config
        self._services = services
        self._events = events
        self._hooks = hooks

        self._trusted: dict[str, LifecycleManager] = {}
        self._sandboxed: dict[str, SandboxProcessManager] = {}
        self._validator = ManifestValidator()

    # ── Chargement global ─────────────────────────────────────

    async def load_all(self) -> dict[str, list[str]]:
        """
        Charge tous les plugins en vagues topologiques.

        Entre chaque vague, propage les services exposés (flush)
        pour que la vague suivante y ait accès.
        """
        loaded, failed, skipped = [], [], []
        manifests = []

        plugin_dir = Path(self._config.directory)
        if not plugin_dir.exists():
            logger.warning(f"Dossier plugins introuvable : {plugin_dir}")
            return {"loaded": [], "failed": [], "skipped": []}

        for d in sorted(plugin_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            try:
                manifest = self._validator.load_and_validate(d)
                manifests.append(manifest)
            except Exception as e:
                logger.warning(f"[{d.name}] Manifeste invalide : {e}")
                skipped.append(d.name)

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
        remaining = list(ordered)

        while remaining:
            wave = [m for m in remaining if all(dep in resolved for dep in m.requires)]
            if not wave:
                stuck = [m.name for m in remaining]
                logger.error(f"Chargement bloqué (dépendances manquantes) : {stuck}")
                failed.extend(stuck)
                break

            logger.info(f"⚡ Vague : [{', '.join(m.name for m in wave)}]")

            results = await asyncio.gather(
                *[self._try_load(m) for m in wave],
                return_exceptions=False,
            )

            wave_loaded = []
            for name, ok in results:
                if ok:
                    loaded.append(name)
                    resolved.add(name)
                    wave_loaded.append(name)
                else:
                    failed.append(name)
                    # Cascade : les plugins qui dépendent du plugin raté sont aussi ratés
                    cascade = [
                        m.name
                        for m in remaining
                        if name in m.requires and m.name not in failed
                    ]
                    if cascade:
                        logger.error(f"[{name}] Cascade : {cascade}")
                        failed.extend(cascade)
                        resolved.update(cascade)

            # Flush des services après chaque vague
            self._flush_services(wave_loaded)

            remaining = [
                m for m in remaining if m.name not in resolved and m.name not in failed
            ]

        logger.info(
            f"Plugins — chargés: {len(loaded)}, "
            f"échecs: {len(failed)}, ignorés: {len(skipped)}"
        )
        return {"loaded": loaded, "failed": failed, "skipped": skipped}

    async def _try_load(self, manifest) -> tuple[str, bool]:
        try:
            await self._activate(manifest)
            return manifest.name, True
        except Exception as e:
            logger.error(f"[{manifest.name}] Échec activation : {e}")
            return manifest.name, False

    async def _activate(self, manifest) -> None:
        from ...kernel.api.contract import ExecutionMode  # évite import circulaire

        mode = manifest.execution_mode
        if mode in (ExecutionMode.TRUSTED, ExecutionMode.LEGACY):
            await self._activate_trusted(manifest)
        else:
            await self._activate_sandboxed(manifest)

    async def _activate_trusted(self, manifest) -> None:
        from ...kernel.security.signature import SignatureError, verify_plugin
        from ...kernel.security.validation import ASTScanner

        if self._config.strict_trusted or manifest.execution_mode.value == "trusted":
            try:
                verify_plugin(manifest, self._config.secret_key)
            except SignatureError as e:
                raise LoadError(str(e)) from e

        scanner = ASTScanner()
        scan = scanner.scan(manifest.plugin_dir, whitelist=manifest.allowed_imports)
        if not scan.passed:
            logger.warning(f"[{manifest.name}] Scan AST (non bloquant) : {scan}")

        lm = LifecycleManager(
            manifest,
            services=self._services,
            events=self._events,
            hooks=self._hooks,
        )
        await lm.load()
        self._trusted[manifest.name] = lm
        logger.info(f"[{manifest.name}] ✅ TRUSTED")

    async def _activate_sandboxed(self, manifest) -> None:
        from ...kernel.sandbox.process_manager import SandboxConfig
        from ...kernel.security.validation import ASTScanner

        scanner = ASTScanner()
        scan = scanner.scan(manifest.plugin_dir, whitelist=manifest.allowed_imports)
        if not scan.passed:
            raise ValueError(f"[{manifest.name}] Scan AST échoué : {scan}")

        from ...kernel.sandbox.process_manager import SandboxProcessManager

        mgr = SandboxProcessManager(manifest)
        await mgr.start()
        self._sandboxed[manifest.name] = mgr
        logger.info(f"[{manifest.name}] ✅ SANDBOXED")

    # ── Chargement individuel ─────────────────────────────────

    async def load(self, plugin_name: str) -> None:
        plugin_dir = Path(self._config.directory) / plugin_name
        if not plugin_dir.is_dir():
            raise FileNotFoundError(f"Dossier plugin introuvable : {plugin_dir}")

        manifest = self._validator.load_and_validate(plugin_dir)
        already_loaded = set(self._trusted) | set(self._sandboxed)

        for dep in manifest.requires:
            if dep not in already_loaded:
                logger.info(f"[{plugin_name}] Dépendance '{dep}' → chargement...")
                await self.load(dep)

        await self._activate(manifest)
        self._flush_services([plugin_name])
        logger.info(f"[{plugin_name}] ✅ chargé")

    async def reload(self, plugin_name: str) -> None:
        if plugin_name in self._trusted:
            await self._trusted[plugin_name].reload()
            self._flush_services([plugin_name])
        elif plugin_name in self._sandboxed:
            manifest = self._sandboxed[plugin_name].manifest
            await self._sandboxed[plugin_name].stop()
            del self._sandboxed[plugin_name]
            await self._activate_sandboxed(manifest)
        else:
            await self.load(plugin_name)

    async def unload(self, plugin_name: str) -> None:
        if plugin_name in self._trusted:
            await self._trusted[plugin_name].unload()
            del self._trusted[plugin_name]
        elif plugin_name in self._sandboxed:
            await self._sandboxed[plugin_name].stop()
            del self._sandboxed[plugin_name]
        else:
            raise KeyError(f"Plugin '{plugin_name}' non chargé")

    # ── Accès ─────────────────────────────────────────────────

    def get(self, name: str) -> LifecycleManager | SandboxProcessManager:
        if name in self._trusted:
            return self._trusted[name]
        if name in self._sandboxed:
            return self._sandboxed[name]
        available = sorted(list(self._trusted) + list(self._sandboxed))
        raise KeyError(f"Plugin '{name}' non trouvé. Disponibles : {available}")

    def has(self, name: str) -> bool:
        return name in self._trusted or name in self._sandboxed

    def all_names(self) -> list[str]:
        return sorted(list(self._trusted) + list(self._sandboxed))

    def status(self) -> list[dict]:
        result = []
        for lm in self._trusted.values():
            result.append(lm.status())
        for sm in self._sandboxed.values():
            result.append(sm.status())
        return result

    # ── Flush services ────────────────────────────────────────

    def _flush_services(self, plugin_names: list[str]) -> None:
        """Propage les services exposés par chaque plugin vers le container partagé."""
        for name in plugin_names:
            if name in self._trusted:
                updated = self._trusted[name].mems(is_reload=False)
                logger.debug(
                    f"[{name}] 📦 services disponibles : {sorted(updated.keys())}"
                )

    # ── Tri topologique (Kahn) ────────────────────────────────

    @staticmethod
    def _topo_sort(manifests: list) -> list:
        from collections import deque

        by_name = {m.name: m for m in manifests}
        in_degree = {m.name: 0 for m in manifests}
        dependents: dict[str, list[str]] = {m.name: [] for m in manifests}

        for m in manifests:
            for dep in m.requires:
                if dep not in by_name:
                    raise ValueError(
                        f"[{m.name}] Dépendance introuvable : '{dep}'. "
                        f"Disponibles : {sorted(by_name.keys())}"
                    )
                dependents[dep].append(m.name)
                in_degree[m.name] += 1

        queue: deque[str] = deque(
            sorted(name for name, deg in in_degree.items() if deg == 0)
        )
        result = []
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
            raise ValueError(f"Dépendances circulaires détectées : {remaining}")

        return result

    async def shutdown(self) -> None:
        """Décharge tous les plugins proprement."""
        trusted_tasks = [lm.unload() for lm in self._trusted.values()]
        sandbox_tasks = [sm.stop() for sm in self._sandboxed.values()]

        for coro in trusted_tasks + sandbox_tasks:
            try:
                await asyncio.wait_for(coro, timeout=10.0)
            except Exception as e:
                logger.error(f"Erreur déchargement : {e}")

        self._trusted.clear()
        self._sandboxed.clear()
        logger.info("Tous les plugins déchargés.")

    def collect_plugin_routers(self) -> list[tuple[str, Any]]:
        """
        Collecte tous les APIRouter exposés par les plugins Trusted chargés.

        Retourne une liste de (plugin_name, APIRouter) pour chaque plugin
        ayant implémenté get_router().

        Utilisé par Xcore._attach_router() pour monter les routes sur l'app FastAPI.
        """
        routers = []
        for name, lm in self._trusted.items():
            if lm.plugin_router is not None:
                routers.append((name, lm.plugin_router))
        return routers
