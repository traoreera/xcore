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
from ...registry import PluginStateStore
from ..api.contract import PluginHandler
from . import service_contracts as contracts
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

        # Contrôle des dépendances Python (#313) : manifestes activés en attente de
        # contrôle, et tâches de contrôle en cours (référencées pour ne pas être collectées).
        self._pending_dependency_checks: list[Any] = []
        self._dependency_check_tasks: set[asyncio.Task] = set()

        # Table de vérité persistante actif/inactif — survit aux redémarrages.
        # Défaut : <plugins_dir>/../.xcore/plugins_state.json, aucune config requise.
        plugins_dir = Path(self._config.directory)
        state_path = plugins_dir.parent / ".xcore" / "plugins_state.json"
        self._state_store = PluginStateStore(state_path)

    @property
    def state_store(self) -> PluginStateStore:
        return self._state_store

    def discover_names(self) -> list[str]:
        """Liste tous les dossiers de plugins présents sur disque (chargés ou non)."""
        plugin_dir = Path(self._config.directory)
        if not plugin_dir.exists():
            return []
        return sorted(
            d.name
            for d in plugin_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )

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
        disabled: list[str] = []
        manifests = []

        plugin_dir = Path(self._config.directory)
        if not plugin_dir.exists():
            logger.warning("plugin directory not found", path=str(plugin_dir))
            return {"loaded": [], "failed": [], "skipped": [], "disabled": []}

        for d in sorted(plugin_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            if not self._state_store.is_enabled(d.name):
                logger.info("plugin disabled, skipped", plugin=d.name)
                disabled.append(d.name)
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
            return {
                "loaded": [],
                "failed": [],
                "skipped": skipped,
                "disabled": disabled,
            }

        # Contrat de services (#311) : refuser AVANT toute activation le plugin dont un
        # service requis manque ou n'a pas la bonne version. Les services déjà dans le
        # container (noyau : db, cache, scheduler…) comptent comme présents.
        providers, refused = contracts.refuse_unsatisfied(
            manifests, available=self._services.keys()
        )
        for name, reason in refused.items():
            logger.error(
                "plugin refused, service contract not satisfied",
                plugin=name,
                reason=reason,
            )
            failed.append(name)
        manifests = [m for m in manifests if m.name not in refused]
        # Un fournisseur se charge avant ses consommateurs, même sans `requires`.
        service_deps = {
            m.name: contracts.service_dependencies(m, providers) for m in manifests
        }

        if not manifests:
            return {
                "loaded": [],
                "failed": failed,
                "skipped": skipped,
                "disabled": disabled,
            }

        try:
            ordered = _topo_sort(manifests, service_deps)
        except ValueError as e:
            logger.error("dependency sort error", error=str(e))
            return {
                "loaded": [],
                "failed": failed + [m.name for m in manifests],
                "skipped": skipped,
                "disabled": disabled,
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
                            "incompatible dependency version",
                            plugin=m.name,
                            dep=dep.name,
                            available_version=resolved_versions[dep.name],
                            constraint=dep.version_constraint,
                        )
                        deps_ok = False
                        break
                if deps_ok and service_deps[m.name] <= resolved:
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
                processed.add(name)
                if ok:
                    loaded.append(name)
                    resolved.add(name)
                    resolved_versions[name] = manifest.version
                    wave_loaded.append(name)
                else:
                    failed.append(name)
                    if cascade := [
                        m.name
                        for m in remaining
                        if (
                            any(dep.name == name for dep in m.requires)
                            or name in service_deps[m.name]
                        )
                        and m.name not in processed
                    ]:
                        logger.error("cascade failure", plugin=name, dependants=cascade)
                        failed.extend(cascade)
                        processed.update(cascade)

            # Flush des services après chaque vague (uniquement les plugins réussis)
            self._flush_services(wave_loaded)

            remaining = [m for m in remaining if m.name not in processed]

        self._start_dependency_checks()
        logger.info(
            "plugins load summary",
            loaded=len(loaded),
            failed=len(failed),
            skipped=len(skipped),
            disabled=len(disabled),
        )
        return {
            "loaded": loaded,
            "failed": failed,
            "skipped": skipped,
            "disabled": disabled,
        }

    async def _try_load(self, manifest: Any) -> tuple[Any, bool]:
        try:
            await self._activate(manifest)
            return manifest, True
        except Exception as e:
            logger.error("plugin activation failed", plugin=manifest.name, error=str(e))
            return manifest, False

    async def _activate(self, manifest: Any) -> None:
        mode = manifest.execution_mode
        activator = self._activators.get(mode)

        if not activator:
            raise ValueError(f"No activator found for mode {mode}")
        self._queue_dependency_check(manifest)
        handler = await activator.activate(manifest, self)
        try:
            self._check_provisions(manifest)
        except contracts.ServiceContractError:
            await handler.stop()
            raise
        self._handlers[manifest.name] = handler
        logger.info("plugin activated", plugin=manifest.name, mode=mode.value)

    # ── Dépendances Python (#313) ─────────────────────────────

    def _queue_dependency_check(self, manifest: Any) -> None:
        if getattr(self._config, "check_dependencies", True) is not False:
            self._pending_dependency_checks.append(manifest)

    def _start_dependency_checks(self) -> None:
        """
        Lance, HORS du chemin de démarrage, le contrôle des plugins qui viennent d'être
        activés : il dit quels paquets un plugin importe sans les déclarer.

        Différé et dans un thread parce que la première lecture des métadonnées des
        paquets installés coûte ~350 ms (mesuré) — on ne les ajoute pas au boot. Un
        avertissement, pas un refus : le paquet est peut-être installé ici, c'est chez le
        client suivant qu'il manquera. Le contrôle bloquant est celui de la CI de
        l'auteur (`xcore-plugin-check`).
        """
        manifests, self._pending_dependency_checks = self._pending_dependency_checks, []
        if not manifests:
            return
        task = asyncio.create_task(
            asyncio.to_thread(_report_undeclared_dependencies, manifests)
        )
        self._dependency_check_tasks.add(task)
        task.add_done_callback(self._dependency_check_tasks.discard)

    async def wait_dependency_checks(self, timeout: float | None = None) -> None:
        """Attend la fin des contrôles de dépendances en cours (tests, arrêt propre)."""
        if tasks := set(self._dependency_check_tasks):
            await asyncio.wait(tasks, timeout=timeout)

    # ── Contrat de services (#311) ────────────────────────────

    def _check_provisions(self, manifest: Any) -> None:
        """Un plugin doit avoir exporté, une fois chargé, ce que son manifeste promet."""
        if missing := contracts.missing_provisions(manifest, self._services.keys()):
            raise contracts.ServiceContractError(
                f"le plugin '{manifest.name}' déclare fournir {missing} "
                "(provides_services) mais ne l'a pas exporté à la fin de on_load"
            )

    def _loaded_providers(self) -> dict[str, contracts.Provider]:
        """`service → fournisseur` pour les plugins actuellement chargés."""
        manifests = [
            m
            for m in (getattr(h, "manifest", None) for h in self._handlers.values())
            if m is not None
        ]
        return contracts.index_providers(manifests)[0]

    def _find_provider_on_disk(self, service: str) -> str | None:
        """Plugin installé (chargé ou non) dont le manifeste déclare fournir `service`."""
        for name in self.discover_names():
            if not self._state_store.is_enabled(name):
                continue
            try:
                manifest, _, _ = self._validator.load_and_validate(
                    Path(self._config.directory) / name
                )
            except (
                Exception
            ):  # noqa: BLE001 - un manifeste illisible n'est pas un fournisseur
                continue
            if any(p.name == service for p in manifest.provides_services):
                return manifest.name
        return None

    async def _ensure_required_services(self, manifest: Any) -> None:
        """
        Chargement individuel : charge au besoin les fournisseurs, puis vérifie le contrat.
        Lève ServiceContractError — le plugin n'est alors pas activé.
        """
        for req in getattr(manifest, "requires_services", None) or []:
            if req.name in self._services or req.name in self._loaded_providers():
                continue
            provider = self._find_provider_on_disk(req.name)
            if provider is not None and provider != manifest.name:
                logger.info(
                    "loading service provider",
                    plugin=manifest.name,
                    service=req.name,
                    provider=provider,
                )
                await self.load(provider)
        if reasons := contracts.unmet_requirements(
            manifest, self._loaded_providers(), available=self._services.keys()
        ):
            raise contracts.ServiceContractError(
                f"Plugin '{manifest.name}' refusé — " + " ; ".join(reasons)
            )

    def _warn_broken_consumers(self, provider_name: str) -> None:
        """Après le reload d'un fournisseur : dire quels consommateurs chargés ne suivent plus."""
        providers = self._loaded_providers()
        for name, handler in self._handlers.items():
            manifest = getattr(handler, "manifest", None)
            if manifest is None or name == provider_name:
                continue
            if provider_name not in contracts.service_dependencies(manifest, providers):
                continue
            if reasons := contracts.unmet_requirements(
                manifest, providers, available=self._services.keys()
            ):
                logger.error(
                    "service contract broken by provider reload",
                    plugin=name,
                    provider=provider_name,
                    reason=" ; ".join(reasons),
                )

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
                logger.info("loading dependency", plugin=plugin_name, dep=dep_name)
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

        await self._ensure_required_services(manifest)
        await self._activate(manifest)
        self._flush_services([plugin_name])
        self._start_dependency_checks()
        logger.info("plugin loaded", plugin=plugin_name)

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
        self._start_dependency_checks()
        self._warn_broken_consumers(plugin_name)

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

        async def _stop_one(name: str, handler: PluginHandler) -> None:
            try:
                await asyncio.wait_for(handler.stop(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("plugin_stop_timeout", plugin=name)
            except Exception as e:
                logger.error("plugin_stop_error", plugin=name, error=str(e))

        if self._handlers:
            tasks = [
                _stop_one(name, handler) for name, handler in self._handlers.items()
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        self._handlers.clear()
        self._pending_dependency_checks.clear()
        await self.wait_dependency_checks(timeout=2.0)
        logger.info("all plugins unloaded")

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


def _report_undeclared_dependencies(manifests: list[Any]) -> None:
    """Exécuté dans un thread : un avertissement par plugin qui importe sans déclarer."""
    from ..security.dependencies import check_plugin_dependencies

    for manifest in manifests:
        try:
            report = check_plugin_dependencies(manifest.plugin_dir)
        except Exception as e:  # noqa: BLE001 - un contrôle de confort ne bloque rien
            logger.debug("dependency check skipped", plugin=manifest.name, error=str(e))
            continue
        if report.ok:
            continue
        logger.warning(
            "plugin imports undeclared dependencies",
            plugin=manifest.name,
            missing=sorted(report.missing),
            declared_in=report.sources or "nowhere",
            hint="declare them in the plugin's pyproject.toml, requirements.txt or "
            "`dependencies:` (plugin.yaml); check with xcore-plugin-check",
        )


# FIX #8 : fonction module-level (pas de méthode statique) — n'a pas besoin de l'instance
def _topo_sort(
    manifests: list[Any], extra_deps: dict[str, set[str]] | None = None
) -> list[Any]:
    """
    Tri topologique des manifestes selon leurs dépendances (algorithme de Kahn).

    `extra_deps` : dépendances implicites (plugin → fournisseurs de ses services
    requis, #311), ajoutées à celles de `requires`.
    """
    manifest_map = {m.name: m for m in manifests}
    resolver = DependencyResolver()
    for m in manifests:
        requires = [
            dep.name if hasattr(dep, "name") else str(dep) for dep in m.requires
        ]
        for extra in sorted((extra_deps or {}).get(m.name, ())):
            if extra not in requires:
                requires.append(extra)
        resolver.add(m.name, requires)
    try:
        ordered_names = resolver.resolve()
    except (CircularDependencyError, MissingDependencyError) as e:
        raise ValueError(str(e)) from e
    return [manifest_map[name] for name in ordered_names]
