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
from .activator import (
    ActivatorRegistry,
    EphemeralActivator,
    SandboxedActivator,
    TrustedActivator,
)

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
        caller: Any = None,
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
        self._activators.register(ExecutionMode.EPHEMERAL, EphemeralActivator())

        self._validator = ManifestValidator()

    # ── Chargement global ─────────────────────────────────────

    async def load_all(self) -> dict[str, list[str]]:
        """
        Charge tous les plugins en vagues topologiques.

        Entre chaque vague, propage les services exposés (flush)
        pour que la vague suivante y ait accès.
        """
        loaded: list[str] = []
        failed: list[str] = []
        skipped: list[str] = []
        manifests = []

        plugin_dir = Path(self._config.directory)
        if not plugin_dir.exists():
            logger.warning("plugins_folder_not_found", path=str(plugin_dir))
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
                        "framework_version_incompatible",
                        plugin=manifest.name,
                        required=manifest.framework_version,
                        current=frameversion,
                    )
            except Exception as e:
                logger.warning("invalid_manifest", plugin=d.name, error=str(e))
                skipped.append(d.name)

        if not manifests:
            return {"loaded": [], "failed": [], "skipped": skipped}

        try:
            ordered = _topo_sort(manifests)
        except ValueError as e:
            logger.error("dependency_sort_error", error=str(e))
            return {
                "loaded": [],
                "failed": [m.name for m in manifests],
                "skipped": skipped,
            }

        # FIX #2 : deux ensembles distincts — "chargé avec succès" vs "traité"
        # resolved  = plugins chargés avec succès (leurs services sont disponibles)
        # processed = tous les plugins déjà traités (succès OU échec), pour filtrer `remaining`
        resolved: set[str] = set()
        resolved_versions: dict[str, str] = {}
        processed: set[str] = set()
        remaining = list(ordered)

        while remaining:
            wave = []
            for m in remaining:
                deps_ok = True
                for dep in m.requires:
                    if dep.name not in resolved:
                        deps_ok = False
                        break
                    if not dep.is_compatible(resolved_versions.get(dep.name, "1.0")):
                        logger.error(
                            "incompatible_dependency_version",
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
                    "loading_blocked",
                    blocked_plugins=stuck,
                )
                failed.extend(stuck)
                break

            logger.info("loading_wave", plugins=[m.name for m in wave])

            results = await asyncio.gather(
                *[self._try_load(m) for m in wave],
                return_exceptions=False,
            )

            wave_loaded = []
            for manifest, ok in results:
                name = manifest.name
                processed.add(name)
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
                        and m.name not in processed
                    ]
                    if cascade:
                        logger.error(
                            "cascading_failure", plugin=name, dependents=cascade
                        )
                        failed.extend(cascade)
                        processed.update(cascade)

            # Flush des services après chaque vague (uniquement les plugins réussis)
            self._flush_services(wave_loaded)

            remaining = [m for m in remaining if m.name not in processed]

        logger.info(
            "plugin_loading_report",
            loaded=len(loaded),
            failed=len(failed),
            skipped=len(skipped),
        )
        return {"loaded": loaded, "failed": failed, "skipped": skipped}

    async def _try_load(self, manifest: Any) -> tuple[Any, bool]:
        try:
            await self._activate(manifest)
            return manifest, True
        except Exception as e:
            logger.error("plugin_activation_failed", plugin=manifest.name, error=str(e))
            return manifest, False

    async def _activate(self, manifest: Any) -> None:
        mode = manifest.execution_mode
        activator = self._activators.get(mode)

        if not activator:
            raise ValueError(f"No activator found for mode {mode}")
        handler = await activator.activate(manifest, self)
        self._handlers[manifest.name] = handler
        logger.info("plugin_activated", plugin=manifest.name, mode=mode.value)

    # ── Chargement individuel ─────────────────────────────────

    async def load(self, plugin_name: str) -> None:
        plugin_dir = Path(self._config.directory) / plugin_name
        if not plugin_dir.is_dir():
            raise FileNotFoundError(f"Plugin folder not found: {plugin_dir}")

        manifest, valid, _ = self._validator.load_and_validate(plugin_dir)
        if not valid:
            raise ValueError(f"Plugin '{plugin_name}': incompatible framework version")

        # FIX #3 : vérification des contraintes de version, cohérente avec load_all()
        for dep in manifest.requires:
            dep_name = dep.name if hasattr(dep, "name") else str(dep)
            if dep_name not in self._handlers:
                logger.info("loading_dependency", plugin=plugin_name, dep=dep_name)
                await self.load(dep_name)
            else:
                dep_handler = self._handlers[dep_name]
                dep_version = getattr(
                    getattr(dep_handler, "manifest", None), "version", "1.0"
                )
                if not dep.is_compatible(dep_version):
                    raise ValueError(
                        f"Plugin '{plugin_name}': dependency '{dep_name}' version "
                        f"'{dep_version}' does not satisfy constraint '{dep.version_constraint}'"
                    )

        await self._activate(manifest)
        self._flush_services([plugin_name])
        logger.info("plugin_loaded", plugin=plugin_name)

    async def reload(self, plugin_name: str) -> None:
        if plugin_name not in self._handlers:
            await self.load(plugin_name)
            return

        handler = self._handlers[plugin_name]

        # FIX #5 : supprimer l'ancien handler avant de tenter le rechargement
        # pour éviter de laisser un handler en état cassé si stop() échoue
        if hasattr(handler, "reload") and callable(handler.reload):
            await handler.reload()
        else:
            manifest = getattr(handler, "manifest", getattr(handler, "_manifest", None))
            del self._handlers[plugin_name]  # retrait préventif avant stop
            try:
                await handler.stop()
            except Exception as e:
                logger.error("error_stopping_plugin", plugin=plugin_name, error=str(e))
            # Réactivation quoi qu'il arrive (le handler précédent est déjà retiré)
            await self._activate(manifest)
        self._flush_services([plugin_name])

    async def unload(self, plugin_name: str) -> None:
        if plugin_name not in self._handlers:
            raise KeyError(f"Plugin '{plugin_name}' not loaded")
        await self._handlers[plugin_name].stop()
        del self._handlers[plugin_name]

    # ── Accès ─────────────────────────────────────────────────

    def get(self, name: str) -> PluginHandler:
        if name in self._handlers:
            return self._handlers[name]
        # FIX #7 : pas de sorted() inutile dans le message d'erreur
        available = list(self._handlers.keys())
        raise KeyError(f"Plugin '{name}' not found. Available: {available}")

    def get_manifest(self, name: str) -> Any | None:
        """Retourne le PluginManifest d'un plugin chargé, ou None."""
        handler = self._handlers.get(name)
        return None if handler is None else getattr(handler, "manifest", None)

    def has(self, name: str) -> bool:
        return name in self._handlers

    def all_names(self) -> list[str]:
        return sorted(list(self._handlers.keys()))

    def status(self) -> list[dict]:
        return [h.status() for h in self._handlers.values()]

    # ── Flush services ────────────────────────────────────────

    def _flush_services(self, plugin_names: list[str]) -> None:
        """
        Propage les services exposés par chaque plugin vers le container partagé.
        N'est appelé que pour les plugins chargés avec succès.
        """
        for name in plugin_names:
            handler = self._handlers.get(name)
            if handler and hasattr(handler, "propagate_services"):
                updated = handler.propagate_services(is_reload=False)
                logger.debug(
                    "services_propagated", plugin=name, services=sorted(updated.keys())
                )

    # ── Arrêt ─────────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Décharge tous les plugins proprement, en parallèle avec timeout individuel."""

        # FIX #1 : gather avec timeout par handler, return_exceptions=True pour ne pas
        # interrompre les autres plugins si l'un d'eux échoue
        async def _stop_one(name: str, handler: PluginHandler) -> None:
            try:
                await asyncio.wait_for(handler.stop(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("plugin_stop_timeout", plugin=name)
            except Exception as e:
                logger.error("plugin_stop_error", plugin=name, error=str(e))

        await asyncio.gather(
            *[_stop_one(name, h) for name, h in self._handlers.items()],
            return_exceptions=True,
        )

        self._handlers.clear()
        logger.info("all_plugins_unloaded")

    # ── Collecte routes / middlewares ─────────────────────────

    def collect_plugin_routers(self) -> list[tuple[str, Any]]:
        """
        Collecte tous les APIRouter exposés par les plugins Trusted chargés.

        Retourne une liste de (plugin_name, APIRouter) pour chaque plugin
        ayant implémenté get_router().

        Utilisé par Xcore._attach_router() pour monter les routes sur l'app FastAPI.
        """
        return [
            (name, handler.plugin_router)
            for name, handler in self._handlers.items()
            if getattr(handler, "plugin_router", None) is not None
        ]

    def collect_app_state(self) -> list[Any]:
        """
        Collecte tous les middlewares exposés par les plugins chargés.

        Retourne une liste de (plugin_name, middleware) pour chaque plugin
        ayant implémenté add_middlewares().

        FIX #4 : retourne des tuples (name, middleware) comme collect_plugin_routers,
        pour une API symétrique et un meilleur support du debug.

        Utilisé par Xcore._attach_middlewares() pour monter les middlewares sur l'app FastAPI.
        """
        return [
            {"name": name, "states": handler.plugin_middlewares}
            for name, handler in self._handlers.items()
            if getattr(handler, "plugin_middlewares", None) is not None
        ]


# FIX #8 : fonction module-level (pas de méthode statique) — n'a pas besoin de l'instance
def _topo_sort(manifests: list[Any]) -> list[Any]:
    """Tri topologique des manifestes selon leurs dépendances (algorithme de Kahn)."""
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
