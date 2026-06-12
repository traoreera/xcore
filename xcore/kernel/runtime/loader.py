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
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..context import KernelContext

from xcore.registry.resolver import (
    CircularDependencyError,
    DependencyResolver,
    MissingDependencyError,
)

from ...kernel.observability import get_logger
from ...kernel.security.validation import ManifestValidator
from ..api.contract import PluginHandler
from .activator import ActivatorRegistry, SandboxedActivator, TrustedActivator

logger = get_logger("xcore.runtime.loader")


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
        ctx: "KernelContext",
        caller=None,
    ) -> None:
        from ...kernel.api.contract import ExecutionMode

        self._ctx = ctx
        self._config = ctx.config
        self._services = ctx.services.as_dict() if ctx.services else {}
        self._events = ctx.events
        self._hooks = ctx.hooks
        self._registry = ctx.registry
        self._metrics = ctx.metrics
        self._tracer = ctx.tracer
        self._health = ctx.health
        self._caller = caller

        # handlers: name -> PluginHandler (Trusted or Sandboxed)
        self._handlers: dict[str, PluginHandler] = {}

        # Activator registry (Strategy Pattern)
        self._activators = ActivatorRegistry()
        self._activators.register(ExecutionMode.TRUSTED, TrustedActivator())
        self._activators.register(ExecutionMode.SANDBOXED, SandboxedActivator())
        self._activators.register(ExecutionMode.LEGACY, TrustedActivator())

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
            logger.warning("plugin directory not found", path=str(plugin_dir))
            return {"loaded": [], "failed": [], "skipped": []}

        for d in sorted(plugin_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            try:
                manifest, validate_version, frameversion = (
                    self._validator.load_and_validate(d)
                )
                if validate_version:
                    manifests.append(manifest)
                else:
                    logger.warning(
                        "incompatible framework version",
                        plugin=manifest.name,
                        required=manifest.framework_version,
                        current=frameversion,
                    )
            except Exception as e:
                logger.warning("invalid manifest", plugin=d.name, error=str(e))
                skipped.append(d.name)

        if not manifests:
            return {"loaded": [], "failed": [], "skipped": skipped}

        try:
            ordered = self._topo_sort(manifests)
        except ValueError as e:
            logger.error("dependency sort error", error=str(e))
            return {
                "loaded": [],
                "failed": [m.name for m in manifests],
                "skipped": skipped,
            }

        resolved: set[str] = set()
        resolved_versions: dict[str, str] = {}  # name -> version
        remaining = list(ordered)

        while remaining:
            wave = []
            for m in remaining:
                deps_ok = True
                for dep in m.requires:
                    if dep.name not in resolved:
                        deps_ok = False
                        break
                    # Vérifie la contrainte de version
                    if not dep.is_compatible(resolved_versions.get(dep.name, "1.0")):
                        logger.error(
                            "incompatible dependency version",
                            plugin=m.name,
                            dep=dep.name,
                            available_version=resolved_versions[dep.name],
                            constraint=dep.version_constraint,
                        )
                        deps_ok = False
                        break
                if deps_ok:
                    wave.append(m)

            if not wave:
                stuck = [m.name for m in remaining]
                logger.error(
                    "load blocked, missing or incompatible dependencies",
                    blocked_plugins=stuck,
                )
                failed.extend(stuck)
                break

            logger.info("loading wave", plugins=[m.name for m in wave])

            results = await asyncio.gather(
                *[self._try_load(m) for m in wave],
                return_exceptions=False,
            )

            wave_loaded = []
            for manifest, ok in results:
                name = manifest.name
                if ok:
                    loaded.append(name)
                    resolved.add(name)
                    resolved_versions[name] = manifest.version
                    wave_loaded.append(name)
                else:
                    failed.append(name)
                    # Cascade : les plugins qui dépendent du plugin raté sont aussi ratés
                    cascade = [
                        m.name
                        for m in remaining
                        if any(dep.name == name for dep in m.requires)
                        and m.name not in failed
                    ]
                    if cascade:
                        logger.error("cascade failure", plugin=name, dependants=cascade)
                        failed.extend(cascade)
                        resolved.update(cascade)

            # Flush des services après chaque vague
            self._flush_services(wave_loaded)

            remaining = [
                m for m in remaining if m.name not in resolved and m.name not in failed
            ]

        logger.info(
            "plugins load summary",
            loaded=len(loaded),
            failed=len(failed),
            skipped=len(skipped),
        )
        return {"loaded": loaded, "failed": failed, "skipped": skipped}

    async def _try_load(self, manifest) -> tuple[Any, bool]:
        try:
            await self._activate(manifest)
            return manifest, True
        except Exception as e:
            logger.error("plugin activation failed", plugin=manifest.name, error=str(e))
            return manifest, False

    async def _activate(self, manifest) -> None:
        mode = manifest.execution_mode
        activator = self._activators.get(mode)

        if not activator:
            raise ValueError(f"Aucun activateur trouvé pour le mode {mode}")
        handler = await activator.activate(manifest, self)
        self._handlers[manifest.name] = handler
        logger.info("plugin activated", plugin=manifest.name, mode=mode.value)

    # ── Chargement individuel ─────────────────────────────────

    async def load(self, plugin_name: str) -> None:
        plugin_dir = Path(self._config.directory) / plugin_name
        if not plugin_dir.is_dir():
            raise FileNotFoundError(f"Dossier plugin introuvable : {plugin_dir}")

        manifest, valid, _ = self._validator.load_and_validate(plugin_dir)
        if not valid:
            raise ValueError(f"Plugin '{plugin_name}' : version framework incompatible")
        for dep in manifest.requires:
            dep_name = dep.name if hasattr(dep, "name") else str(dep)
            if dep_name not in self._handlers:
                logger.info("loading dependency", plugin=plugin_name, dep=dep_name)
                await self.load(dep_name)

        await self._activate(manifest)
        self._flush_services([plugin_name])
        logger.info("plugin loaded", plugin=plugin_name)

    async def reload(self, plugin_name: str) -> None:
        if plugin_name not in self._handlers:
            await self.load(plugin_name)
            return

        handler = self._handlers[plugin_name]
        if hasattr(handler, "reload") and callable(handler.reload):
            await handler.reload()
            self._flush_services([plugin_name])
        else:
            manifest = handler.manifest
            await handler.stop()
            await self._activate(manifest)
            self._flush_services([plugin_name])

    async def unload(self, plugin_name: str) -> None:
        if plugin_name in self._handlers:
            await self._handlers[plugin_name].stop()
            del self._handlers[plugin_name]
        else:
            raise KeyError(f"Plugin '{plugin_name}' non chargé")

    # ── Accès ─────────────────────────────────────────────────

    def get(self, name: str) -> PluginHandler:
        if name in self._handlers:
            return self._handlers[name]
        available = sorted(list(self._handlers.keys()))
        raise KeyError(f"Plugin '{name}' non trouvé. Disponibles : {available}")

    def get_manifest(self, name: str):
        """Retourne le PluginManifest d'un plugin chargé, ou None."""
        handler = self._handlers.get(name)
        if handler is None:
            return None
        return getattr(handler, "manifest", None)

    def has(self, name: str) -> bool:
        return name in self._handlers

    def all_names(self) -> list[str]:
        return sorted(list(self._handlers.keys()))

    def status(self) -> list[dict]:
        return [h.status() for h in self._handlers.values()]

    # ── Flush services ────────────────────────────────────────

    def _flush_services(self, plugin_names: list[str]) -> None:
        """Propage les services exposés par chaque plugin vers le container partagé."""
        for name in plugin_names:
            handler = self._handlers.get(name)
            if handler and hasattr(handler, "propagate_services"):
                updated = handler.propagate_services(is_reload=False)
                logger.debug(
                    "services propagés", plugin=name, services=sorted(updated.keys())
                )

    # ── Tri topologique (Kahn) ────────────────────────────────
    @staticmethod
    def _topo_sort(manifests: list) -> list:
        manifest_map = {m.name: m for m in manifests}
        resolver = DependencyResolver()
        for m in manifests:
            requires = [
                dep.name if hasattr(dep, "name") else str(dep) for dep in m.requires
            ]
            resolver.add(m.name, requires)
        try:
            ordered_names = resolver.resolve()
        except (CircularDependencyError, MissingDependencyError) as e:
            raise ValueError(str(e)) from e
        return [manifest_map[name] for name in ordered_names]

    async def shutdown(self) -> None:
        """Décharge tous les plugins proprement."""
        tasks = [h.stop() for h in self._handlers.values()]

        for coro in tasks:
            try:
                await asyncio.wait_for(coro, timeout=10.0)
            except Exception as e:
                logger.error("unload error", error=str(e))

        self._handlers.clear()
        logger.info("all plugins unloaded")

    def collect_plugin_routers(self) -> list[tuple[str, Any]]:
        """
        Collecte tous les APIRouter exposés par les plugins Trusted chargés.

        Retourne une liste de (plugin_name, APIRouter) pour chaque plugin
        ayant implémenté get_router().

        Utilisé par Xcore._attach_router() pour monter les routes sur l'app FastAPI.
        """
        routers = []
        for name, handler in self._handlers.items():
            if hasattr(handler, "plugin_router") and handler.plugin_router is not None:
                routers.append((name, handler.plugin_router))
        return routers

    def collect_app_state(self) -> list[Any]:
        """
        Collecte tous les middlewares exposés par les plugins chargés.

        Retourne une liste de middlewares pour chaque plugin ayant implémenté add_middlewares().

        Utilisé par Xcore._attach_middlewares() pour monter les middlewares sur l'app FastAPI.
        """
        middlewares = []
        for name, handler in self._handlers.items():
            if (
                hasattr(handler, "plugin_middlewares")
                and handler.plugin_middlewares is not None
            ):
                middlewares.append(handler.plugin_middlewares)

        return middlewares
