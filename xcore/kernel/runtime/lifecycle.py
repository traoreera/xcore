"""
— Managing the lifecycle of a Trusted plugin.
Responsibilities:
- Import the Python module from the input path
- Inject the services into the instance
- Call the on_load / on_reload / on_unload hooks
- Distribute the exposed services to the shared container (mems)
"""

from __future__ import annotations

import asyncio
import gc
import importlib.util
import inspect
import itertools
import sys
import time
import types
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..context import KernelContext

from ..api.context import PluginContext
from ..api.contract import BasePlugin
from ..observability import get_logger
from ..observability.blocking import watch_blocking
from .plugin_gc import PluginResourceTracker, _ScopedScheduler
from .state_machine import PluginState, StateMachine

logger = get_logger("xcore.runtime.lifecycle")

# Seuil (ms) au-delà duquel un pas synchrone d'un plugin Trusted — du code qui
# tourne entre deux `await` — est signalé comme gelant le event loop (0 = off).
_DEFAULT_LOOP_BLOCK_WARN_MS = 250
# Au plus un avertissement de gel par plugin sur cette fenêtre (secondes).
_LOOP_BLOCK_LOG_INTERVAL_S = 10.0

# Délai avant la collecte qui suit un unload/reload : laisse les tâches annulées,
# les callbacks et les réponses en vol se terminer, et regroupe plusieurs unloads
# rapprochés en UNE seule collecte.
_GC_DELAY_S = 1.0


class _ReleaseWatcher:
    """
    Contrôle de libération des plugins déchargés.

    Une instance de plugin déchargée vit dans des cycles de références (classe,
    module, contexte, tâches) : le comptage de références ne la libère jamais, et
    le GC automatique de Python ne passe en génération ancienne qu'après
    beaucoup d'allocations — mesuré : un cycle mort promu en vieille génération
    n'était pas libéré après 11,5 M d'allocations sur un tas de 3 M d'objets.
    Après un unload/reload, on force donc UNE collecte (différée et regroupée),
    puis on vérifie via un weakref que l'instance a bien disparu — sinon quelque
    chose la référence encore (tâche brute, callback enregistré en dehors du
    ctx…) et on le signale, avec le type de ses référents.
    """

    def __init__(self) -> None:
        self._pending: list[tuple[weakref.ref, str]] = []
        self._handle: asyncio.TimerHandle | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def watch(self, instance: Any, plugin: str, delay: float) -> None:
        try:
            ref = weakref.ref(instance)
        except TypeError:  # classe avec __slots__ sans __weakref__
            return
        self._pending.append((ref, plugin))
        loop = asyncio.get_running_loop()
        if self._handle is not None and self._loop is loop:
            return  # une collecte est déjà programmée : on s'y greffe
        self._loop = loop
        self._handle = loop.call_later(delay, self._collect)

    def _collect(self) -> None:
        self._handle = None
        pending, self._pending = self._pending, []
        started = time.perf_counter()
        collected = gc.collect()
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        leaked = [(ref, plugin) for ref, plugin in pending if ref() is not None]
        logger.debug(
            "plugin garbage collected",
            plugins=sorted({plugin for _, plugin in pending}),
            unreachable_objects=collected,
            duration_ms=duration_ms,
        )
        for ref, plugin in leaked:
            instance = ref()
            if instance is None:
                continue
            referrers = sorted(
                {
                    type(r).__name__
                    for r in gc.get_referrers(instance)
                    if not isinstance(r, types.FrameType)
                }
            )[:8]
            logger.warning(
                "plugin instance still referenced after unload",
                plugin=plugin,
                referrers=referrers,
                hint="a task, callback or service registered outside ctx still holds it",
            )
            del instance


_release_watcher = _ReleaseWatcher()

# Identifiants d'instances « poolées » (plugins Ephemeral) : chacune reçoit son
# propre espace de noms de modules.
_POOLED_INSTANCE_IDS = itertools.count(1)


class LoadError(Exception):
    """Erreur fatale lors du chargement d'un plugin Trusted."""


class LifecycleManager:
    """
    Manages the complete lifecycle of a Trusted plugin in memory.
    """

    PROTECTED_SERVICES = {"db", "cache", "scheduler", "events", "hooks", "database"}

    # Délai accordé aux tâches annulées au unload pour exécuter leurs `finally`
    # avant que le module du plugin soit retiré de sys.modules.
    _TASK_CANCEL_TIMEOUT_S = 2.0

    def __init__(
        self,
        manifest,  # PluginManifest
        ctx: "KernelContext",
        caller=None,
        *,
        pooled: bool = False,
    ) -> None:
        """
        `pooled=True` : instance jetable d'un plugin Ephemeral (plusieurs
        instances du même manifest coexistent). Elle reçoit son propre espace de
        noms `sys.modules` et ne désinscrit pas le plugin du registre à son
        unload — sinon décharger UNE instance cassait les imports paresseux des
        instances sœurs encore actives et retirait du registre un plugin pourtant
        toujours actif.
        """
        self._ctx = ctx
        self.manifest = manifest
        self._module_name = f"xcore_plugin_{manifest.name}"
        if pooled:
            self._module_name += f"__i{next(_POOLED_INSTANCE_IDS)}"
        self._manages_registry = not pooled
        self._services = ctx.services.as_dict() if ctx.services else {}
        self._events = ctx.events
        self._hooks = ctx.hooks
        self._registry = ctx.registry
        self._metrics = ctx.metrics
        self._tracer = ctx.tracer
        self._health = ctx.health
        self._caller = caller

        self._instance: BasePlugin | None = None
        self._module: Any = None
        self._loaded_at: float | None = None
        # APIRouter exposé par le plugin (optionnel)
        self.plugin_router: Any | None = None
        self.plugin_middlewares: dict[Any] = {}

        # Ramasse-miette forcé : ce que le plugin a enregistré (jobs, health
        # checks, abonnements events/hooks) via le PluginContext, et les
        # tâches de fond créées via ctx.spawn_task(). Nettoyés de force au
        # unload, indépendamment de ce que fait on_unload/on_stop.
        self._resource_tracker: PluginResourceTracker | None = None
        self._spawned_tasks: list[asyncio.Task] = []

        # Services injectés par le noyau dans ctx.services (après wrapping
        # tenant/ramasse-miette), au moment du load : nom → objet exact reçu.
        # Sert à distinguer, dans propagate_services(), ce que le plugin a
        # *exporté* de ce qu'il a simplement reçu en injection — ces derniers
        # ne doivent jamais être réécrits dans le container partagé.
        self._injected_services: dict[str, Any] = {}
        # Services que CE plugin a écrits dans le container partagé (nom → objet),
        # retirés au unload pour ne pas laisser un plugin mort appelable.
        self._exported_to_container: dict[str, Any] = {}

        # Gel du event loop par du code synchrone du plugin (voir watch_blocking)
        self._max_block_ms: float = 0.0
        self._last_block_log: float = float("-inf")

        self._sm = StateMachine(
            manifest.name,
            on_change=self._on_state_change,
        )

    # ── État ──────────────────────────────────────────────────

    @property
    def state(self) -> PluginState:
        return self._sm.state

    @property
    def is_ready(self) -> bool:
        return self._sm.is_ready

    @property
    def uptime(self) -> float | None:
        return None if self._loaded_at is None else time.monotonic() - self._loaded_at

    def _on_state_change(self, old: PluginState, new: PluginState) -> None:
        logger.debug(
            "state transition",
            plugin=self.manifest.name,
            from_state=old.value,
            to_state=new.value,
        )
        if self._events:
            self._events.emit_sync(
                f"plugin.{self.manifest.name}.state_changed",
                {"from": old.value, "to": new.value},
            )

    # ── Interface PluginHandler ───────────────────────────────

    async def start(self) -> None:
        """Alias de load() pour la conformité PluginHandler."""
        await self.load()

    async def stop(self) -> None:
        """Alias de unload() pour la conformité PluginHandler."""
        await self.unload()

    # ── Chargement ────────────────────────────────────────────

    async def load(self) -> None:
        self._sm.transition("load")
        try:
            await self._do_load()
            self.propagate_services(is_reload=False)
            self._sm.transition("ok")
            self._loaded_at = time.monotonic()
            logger.info(
                "plugin loaded",
                plugin=self.manifest.name,
                timeout_s=self.manifest.resources.timeout_seconds,
            )
        except Exception as e:
            self._sm.transition("error")
            logger.exception(
                "plugin load failed", plugin=self.manifest.name, error=str(e)
            )
            await self._cleanup_after_failure()
            raise LoadError(f"[{self.manifest.name}] Loading failed: {e}") from e

    async def _do_load(self) -> None:
        entry = self.manifest.plugin_dir / self.manifest.entry_point
        if not entry.exists():
            raise LoadError(f"Not found entry point: {entry}")

        module_name = self._module_name
        package_name = module_name

        # Crée un package namespace virtuel pour isoler le plugin
        if package_name not in sys.modules:
            sys.modules[package_name] = types.ModuleType(package_name)
            # Isolation namespace : utilise un nom de module unique par plugin
            # pour éviter les conflits entre plugins ayant des fichiers du même nom
            src_dir = str(self.manifest.plugin_dir / "src")
            sys.modules[package_name].__path__ = [src_dir]

        # N'ajoute pas src_dir à sys.path global pour éviter les conflits
        # Le module est importé via son package namespace isolé
        self._module = self._import_module(f"{module_name}.main", entry)

        if not hasattr(self._module, "Plugin"):
            raise LoadError(f"class Plugin() not found in {entry}")

        cls = self._module.Plugin
        self._instance = self._instantiate(cls)

        if not hasattr(self._instance, "handle"):
            raise LoadError(
                "the plugin not respect contrat BasePlugin"
                " (missing method async handle(action, payload))"
            )

        # Injection du contexte riche
        params = self._ctx.as_plugin_context_params(
            plugin_name=self.manifest.name,
            caller=self._caller,
        )
        ctx = PluginContext(
            **params,
            env=self.manifest.env,
            config=getattr(self.manifest, "extra", {}),
        )

        # Si la tenancy est activée, on wrappe les services avec les adapteurs
        # tenant-aware dès le chargement. Les wrappers lisent le tenant depuis un
        # ContextVar asyncio — le plugin n'a rien à changer.
        tenancy = getattr(self._ctx.config, "tenancy", None)
        if tenancy is not None and tenancy.enabled:
            from ...kernel.tenancy.services import wrap_services_for_tenant

            ctx.services = wrap_services_for_tenant(
                ctx.services,
                isolate_cache=tenancy.isolate_cache,
                isolate_db=tenancy.isolate_db,
                isolate_scheduler=tenancy.isolate_scheduler,
            )

        # Ramasse-miette forcé : on intercepte scheduler/health/events/hooks
        # pour mémoriser ce que CE plugin y enregistre pendant on_load, afin
        # de tout désinscrire au unload sans dépendre de on_unload/on_stop.
        tracker = PluginResourceTracker(self.manifest.name)
        ctx.events = tracker.wrap_events(ctx.events)
        ctx.hooks = tracker.wrap_hooks(ctx.hooks)
        ctx.health = tracker.wrap_health(ctx.health)
        if ctx.services.get("scheduler") is not None:
            ctx.services = dict(ctx.services)
            ctx.services["scheduler"] = tracker.wrap_scheduler(
                ctx.services["scheduler"]
            )
        self._resource_tracker = tracker
        ctx._task_sink = self._spawned_tasks
        self._injected_services = dict(ctx.services)

        if hasattr(self._instance, "_inject_context"):
            await self._instance._inject_context(ctx)
        elif hasattr(self._instance, "env_variable"):
            # rétro-compatibilité v1
            await self._instance.env_variable(self.manifest.env)

        await self._invoke_hooks(["on_init", "on_load", "on_start"])

        # Enregistre les schémas @schema dans le SchemaRegistry global
        if hasattr(self._instance, "_register_schemas"):
            self._instance._register_schemas(self.manifest.name)

        # Collecte le router HTTP custom si le plugin en expose un
        self._collect_router()
        self._collect_middlewares()

    async def _invoke_hooks(self, hook_names: list[str]) -> None:
        """Invoque une série de hooks sur l'instance s'ils existent."""
        if not self._instance:
            return
        for name in hook_names:
            hook = getattr(self._instance, name, None)
            if hook and callable(hook):
                try:
                    if inspect.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()
                except Exception as e:
                    logger.error(
                        "error in hook",
                        plugin=self.manifest.name,
                        hook=name,
                        erreur=str(e),
                    )
                    raise

    def _instantiate(self, cls) -> BasePlugin:
        """Instancie le plugin en injectant services si possible."""
        try:
            sig = inspect.signature(cls.__init__)
            if "services" in sig.parameters:
                instance = cls(services=self._services)
            else:
                instance = cls()
                # Injection directe sur l'attribut (TrustedBase rétro-compat)
                if hasattr(instance, "_services"):
                    instance._services = self._services
        except (ValueError, TypeError):
            instance = cls()
        return instance

    @staticmethod
    def _import_module(name: str, path: Path) -> Any:
        if name in sys.modules:
            del sys.modules[name]
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise LoadError(f"Impossible to create spec for {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    # ── Appel ─────────────────────────────────────────────────

    def _loop_block_warn_ms(self) -> float:
        value = getattr(self._ctx.config, "loop_block_warn_ms", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return _DEFAULT_LOOP_BLOCK_WARN_MS
        return value

    def _on_loop_block(self, action: str, seconds: float) -> None:
        """Un pas synchrone du plugin vient de geler le event loop `seconds`."""
        self._max_block_ms = max(self._max_block_ms, seconds * 1000)
        now = time.monotonic()
        if now - self._last_block_log < _LOOP_BLOCK_LOG_INTERVAL_S:
            return
        self._last_block_log = now
        logger.warning(
            "plugin blocked the event loop",
            plugin=self.manifest.name,
            action=action,
            blocked_ms=round(seconds * 1000),
            hint="synchronous CPU/IO between two awaits; use await, "
            "asyncio.to_thread, or execution_mode: sandboxed",
        )

    async def call(self, action: str, payload: dict) -> dict:
        if self._instance is None:
            raise RuntimeError(f"[{self.manifest.name}] not loaded")

        if not self._sm.is_available:
            raise RuntimeError(
                f"[{self.manifest.name}] plugin in state {self._sm.state}"
            )

        timeout = self.manifest.resources.timeout_seconds
        try:
            result = await asyncio.wait_for(
                watch_blocking(
                    self._instance.handle(action, payload),
                    self._loop_block_warn_ms(),
                    lambda seconds: self._on_loop_block(action, seconds),
                ),
                timeout=timeout if timeout > 0 else None,
            )
        except asyncio.TimeoutError:
            return {
                "status": "error",
                "msg": f"Timeout après {timeout}s",
                "code": "timeout",
            }
        except Exception:
            raise

        return (
            result if isinstance(result, dict) else {"status": "ok", "result": result}
        )

    def get_action_permissions(self, action: str) -> list[str]:
        """
        Permissions requises pour une action, déclarées via
        @action(name, permissions=[...]). Liste vide si l'action n'en déclare
        pas, si le plugin n'utilise pas AutoDispatchMixin, ou si l'action est
        inconnue — ne jamais lever ici, un ActionPermissionMiddleware strict
        s'appuie dessus avant même de savoir si l'action existe.
        """
        instance = self._instance
        if instance is None:
            return []
        if not getattr(instance, "_action_map_built", False):
            build = getattr(instance, "_build_action_map", None)
            if build is None:
                return []
            build()
        method = getattr(instance, "_action_map", {}).get(action)
        return list(getattr(method, "_xcore_action_permissions", None) or [])

    # ── Reload ────────────────────────────────────────────────

    async def reload(self) -> None:
        self._sm.transition("reload")
        try:
            await self._invoke_hooks(["on_reload"])
            await self._do_unload()
            await self._do_load()
            # is_reload=True : force la mise à jour des services existants
            self.propagate_services(is_reload=True)
            self._sm.transition("ok")
            self._loaded_at = time.monotonic()
            logger.info("plugin reloaded", plugin=self.manifest.name)
        except Exception as e:
            self._sm.transition("error")
            logger.error(
                "plugin reload failed", plugin=self.manifest.name, error=str(e)
            )
            await self._cleanup_after_failure()
            raise LoadError(f"[{self.manifest.name}] failed reload : {e}") from e

    # ── Unload ────────────────────────────────────────────────

    async def unload(self) -> None:
        self._sm.transition("unload")
        try:
            await self._do_unload()
            self._sm.transition("ok")
            logger.info("plugin unloaded", plugin=self.manifest.name)
        except Exception:
            self._sm.transition("error")
            raise

    async def _cleanup_after_failure(self) -> None:
        """
        Ramasse-miette forcé après un load()/reload() raté, sans rappeler les
        hooks du plugin (son état interne est incohérent). Sans ça, ce qu'il a
        déjà enregistré (jobs, abonnements, tâches, module dans sys.modules)
        restait en place alors que le plugin passe en FAILED.
        """
        try:
            await self._do_unload(run_hooks=False)
        except Exception as e:  # pragma: no cover — best-effort
            logger.error(
                "forced cleanup after failure failed",
                plugin=self.manifest.name,
                error=str(e),
            )

    async def _cancel_spawned_tasks(self) -> None:
        """
        Annule les tâches créées via ctx.spawn_task() et ATTEND qu'elles se
        terminent (délai borné) : un simple cancel() ne fait que programmer
        l'annulation, leurs `finally` s'exécutaient donc après que le module du
        plugin ait été retiré de sys.modules.
        """
        current = asyncio.current_task()  # un unload peut venir d'une de ces tâches
        pending = [t for t in self._spawned_tasks if t is not current and not t.done()]
        self._spawned_tasks = []
        for task in pending:
            task.cancel()
        if not pending:
            return
        _, still_running = await asyncio.wait(
            pending, timeout=self._TASK_CANCEL_TIMEOUT_S
        )
        if still_running:
            logger.warning(
                "spawned tasks ignored cancellation",
                plugin=self.manifest.name,
                tasks=sorted(t.get_name() for t in still_running),
                timeout_s=self._TASK_CANCEL_TIMEOUT_S,
            )

    async def _do_unload(self, *, run_hooks: bool = True) -> None:
        if self._instance and run_hooks:
            # Best-effort : on essaie les hooks du plugin, mais une erreur ici
            # ne doit pas empêcher le ramasse-miette forcé ci-dessous — c'est
            # justement le filet de sécurité pour un on_unload/on_stop bâclé.
            try:
                await self._invoke_hooks(["on_stop", "on_unload"])
            except Exception as e:
                logger.error(
                    "on_stop/on_unload hook failed, forcing cleanup anyway",
                    plugin=self.manifest.name,
                    error=str(e),
                )

        # Ramasse-miette forcé : libère tout ce que le plugin a enregistré,
        # qu'il l'ait fait proprement dans ses hooks ou pas.
        if self._resource_tracker is not None:
            self._resource_tracker.cleanup()
            self._resource_tracker = None

        await self._cancel_spawned_tasks()

        if self._registry is not None and self._manages_registry:
            self._registry.unregister(self.manifest.name)

        # `unregister()` ne nettoie que le registre : les services que le plugin
        # a exportés restaient aussi dans le dict partagé du ServiceContainer,
        # donc appelables par les autres plugins (et le plugin déchargé épinglé
        # en mémoire). On ne retire que ce que CE plugin y a mis, tel quel.
        for name, obj in self._exported_to_container.items():
            if self._services.get(name) is obj:
                self._services.pop(name, None)
        self._exported_to_container = {}
        self._injected_services = {}

        # Router HTTP / middlewares du plugin : sans ça, un handler déchargé
        # gardait l'ancien router (et via ses closures l'ancien module), et un
        # reload dont le nouveau code n'en expose plus gardait l'ancien actif.
        self.plugin_router = None
        self.plugin_middlewares = {}

        module_name = self._module_name
        # Nettoie le module principal et le package namespace
        sys.modules.pop(f"{module_name}.main", None)
        sys.modules.pop(module_name, None)
        # Nettoie aussi tous les sous-modules du plugin
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith(f"{module_name}."):
                sys.modules.pop(mod_name, None)
        instance, self._instance = self._instance, None
        self._module = None
        if instance is not None and self._should_watch_release():
            _release_watcher.watch(instance, self.manifest.name, _GC_DELAY_S)
        del instance

    def _should_watch_release(self) -> bool:
        # Les instances poolées (Ephemeral) sont jetées à chaque appel : le GC
        # automatique les gère (jeunes cycles) et une collecte complète par appel
        # coûterait bien plus qu'elle ne rapporte.
        if not self._manages_registry:
            return False
        return getattr(self._ctx.config, "gc_after_unload", True) is not False

    # ── Router HTTP custom ────────────────────────────────────

    def _collect_router(self) -> None:
        """
        Si le plugin expose get_router(), récupère l'APIRouter et le stocke.
        Le PluginLoader le collectera et le passera à Xcore pour montage sur l'app.
        """
        if self._instance is None:
            return
        get_router = getattr(self._instance, "get_router", None)
        if get_router is None:
            get_router = getattr(self._instance, "router", None)

        if not callable(get_router):
            return
        try:
            router = get_router()
            if router is not None:
                self.plugin_router = router
                logger.info(
                    "http router collected",
                    plugin=self.manifest.name,
                    routes=len(getattr(router, "routes", [])),
                )
        except Exception as e:
            logger.error(
                "http router collection error", plugin=self.manifest.name, error=str(e)
            )

    def _collect_middlewares(self) -> None:
        add_middlewares = getattr(self._instance, "add_state", None)
        if add_middlewares is None:
            return

        if not callable(add_middlewares):
            return

        try:
            middlewares = add_middlewares()
            if middlewares is not None:
                self.plugin_middlewares = dict(middlewares)
                logger.info(
                    "middlewares collected",
                    plugin=self.manifest.name,
                    count=len(self.plugin_middlewares),
                )
        except Exception as e:
            logger.error(
                "middlewares collection error", plugin=self.manifest.name, error=str(e)
            )

    # ── Propagation des services (fix #3 v1) ──────────────────

    def _is_injected(self, name: str, obj: Any) -> bool:
        """Vrai si `obj` est exactement l'objet injecté par le noyau sous `name`."""
        return name in self._injected_services and self._injected_services[name] is obj

    @staticmethod
    def _unwrap_proxy(obj: Any) -> Any:
        """Retire tous les niveaux de proxy de ramasse-miette autour d'un service."""
        while isinstance(obj, _ScopedScheduler):
            obj = obj._real
        return obj

    def propagate_services(self, *, is_reload: bool = False) -> dict:
        """
        Propage les services enregistrés par le plugin vers le container partagé.
        Utilise le PluginRegistry pour une gestion plus propre si disponible.
        """
        if self._instance is None:
            return self._services

        # Récupère les services depuis l'instance (convention _services)
        instance_services: dict = getattr(self._instance, "_services", {})

        # Récupère aussi les services déclarés dans le manifeste (ressources)
        manifest_services_config = {}
        if hasattr(self.manifest, "resources") and hasattr(
            self.manifest.resources, "services"
        ):
            manifest_services_config = self.manifest.resources.services
        if not instance_services:
            return self._services

        # if collisions := set(instance_services.keys()) & self.PROTECTED_SERVICES:
        #    raise ValueError(
        #        f"[{self.manifest.name}] Tentative d'écrasement de services protégés "
        # Tentative         f"par le noyau : {collisions}"
        #    )

        # Enregistrement explicite dans le registre pour le scoping/discovery
        # On le fait AVANT de mettre à jour self._services pour que le registre soit
        # la source de vérité et assure la protection des services noyau.
        if self._registry:
            for name, obj in instance_services.items():
                # Service reçu en injection (db, cache, scheduler…), pas exporté
                # par ce plugin : ni à enregistrer ni à réécrire dans le
                # container partagé.
                if self._is_injected(name, obj):
                    continue
                svc_meta = manifest_services_config.get(name, {})
                scope = svc_meta.get("scope", "public")

                try:
                    # register_service lève PermissionError si le service est protégé
                    self._registry.register_service(
                        plugin_name=self.manifest.name,
                        service_name=name,
                        service_obj=obj,
                        metadata={
                            "reloaded": is_reload,
                            "scope": scope,
                            "description": svc_meta.get("description", ""),
                        },
                    )
                except PermissionError:
                    # TrustedBase expose tout `ctx.services` (y compris db/cache/
                    # scheduler) via `self._services` pour la rétro-compatibilité —
                    # ce ne sont pas forcément des services que CE plugin exporte,
                    # potentiellement juste ceux qu'il a reçus en injection. Au
                    # premier boot le registre ne les protège pas encore
                    # (register_core_service() n'a lieu qu'après load_all()), donc
                    # ça passe ; mais dès qu'on recharge/réactive le même plugin
                    # plus tard, le nom est déjà protégé par le noyau. Si c'est
                    # bien le même objet reçu en injection, ce n'est pas une
                    # tentative d'écrasement — on l'ignore. Si c'est un objet
                    # différent, c'est une vraie tentative malveillante : on
                    # relève l'erreur telle quelle. `obj` peut être un proxy de
                    # ramasse-miette (_ScopedScheduler, etc.) posé par ce même
                    # LifecycleManager autour du service réel — on déballe tous
                    # les niveaux de proxy avant de comparer, sinon l'identité
                    # ne matcherait jamais pour un service ainsi enveloppé.
                    underlying = self._unwrap_proxy(obj)
                    if self._registry.is_registered_as(
                        name, obj
                    ) or self._registry.is_registered_as(name, underlying):
                        logger.debug(
                            "skip re-registering kernel-protected service",
                            plugin=self.manifest.name,
                            service=name,
                        )
                    else:
                        raise
        else:
            # Fallback de sécurité si le registre est absent (pour les tests ou configs minimales)
            # On définit une liste minimale de services à protéger
            protected = {"db", "cache", "scheduler", "events", "hooks", "database"}
            if collisions := {
                k
                for k, v in instance_services.items()
                if k in protected and not self._is_injected(k, v)
            }:
                raise PermissionError(
                    f"[{self.manifest.name}] Tentative d'écrasement de services "
                    f"noyau sans registre : {collisions}"
                )

        # Émet un événement pour signaler que les services sont prêts
        if self._events:
            self._events.emit_sync(
                f"plugin.{self.manifest.name}.services_registered",
                {
                    "plugin": self.manifest.name,
                    "is_reload": is_reload,
                    "services": list(instance_services.keys()),
                },
            )

        # Mise à jour du container local (rétro-compatibilité et accès rapide).
        # `self._services` EST le dict partagé du ServiceContainer : on n'y
        # écrit que ce que le plugin a exporté, jamais les services du noyau
        # reçus en injection — sinon un reload y laissait le proxy de
        # ramasse-miette du plugin à la place du vrai service (et chaque reload
        # empilait un proxy de plus, cassant le reload/load suivant de
        # n'importe quel plugin).
        exported = {
            k: v for k, v in instance_services.items() if not self._is_injected(k, v)
        }
        self._exported_to_container.update(exported)
        if is_reload:
            self._services.update(exported)
            logger.info(
                "services updated on reload",
                plugin=self.manifest.name,
                services=sorted(exported.keys()),
            )
        else:
            new_keys = set(exported.keys()) - set(self._services.keys())
            for k in new_keys:
                self._services[k] = exported[k]
            if new_keys:
                logger.info(
                    "services registered",
                    plugin=self.manifest.name,
                    services=sorted(new_keys),
                )

        return self._services

    # ── Status ────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "name": self.manifest.name,
            "mode": "trusted",
            "state": self._sm.state.value,
            "loaded": self._instance is not None,
            "uptime": round(self.uptime, 1) if self.uptime else None,
            "max_loop_block_ms": round(self._max_block_ms),
        }
