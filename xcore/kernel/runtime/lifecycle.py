"""
lifecycle.py — Gestion du cycle de vie d'un plugin Trusted.

Responsabilités :
  - Importer le module Python depuis le chemin d'entrée
  - Injecter les services dans l'instance
  - Appeler les hooks on_load / on_reload / on_unload
  - Propager les services exposés vers le container partagé (mems)
"""
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import sys
import time
from pathlib import Path
from typing import Any

from ..api.contract import BasePlugin
from ..api.context  import PluginContext
from .state_machine import StateMachine, PluginState

logger = logging.getLogger("xcore.runtime.lifecycle")


class LoadError(Exception):
    """Erreur fatale lors du chargement d'un plugin Trusted."""


class LifecycleManager:
    """
    Gère le cycle de vie complet d'un plugin Trusted en mémoire.

    Corrections v2 par rapport à v1 :
      - mems(is_reload) distingue chargement initial et reload (fix #3 v1)
      - Contexte riche (PluginContext) injecté plutôt que dict brut
      - Séparation claire loader / lifecycle / supervisor

    Usage:
        lm = LifecycleManager(manifest, services=shared_dict)
        await lm.load()
        result = await lm.call("ping", {})
        await lm.reload()
        await lm.unload()
    """

    def __init__(
        self,
        manifest,                          # PluginManifest
        services: dict[str, Any],          # container partagé (référence)
        events=None,                       # EventBus optionnel
        hooks=None,                        # HookManager optionnel
    ) -> None:
        self.manifest  = manifest
        self._services = services          # même objet que PluginSupervisor._services
        self._events   = events
        self._hooks    = hooks
        self._instance: BasePlugin | None = None
        self._module: Any = None
        self._loaded_at: float | None = None
        self.plugin_router: Any | None = None  # APIRouter exposé par le plugin (optionnel)
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
        logger.debug(f"[{self.manifest.name}] état : {old.value} → {new.value}")
        if self._events:
            self._events.emit_sync(
                f"plugin.{self.manifest.name}.state_changed",
                {"from": old.value, "to": new.value},
            )

    # ── Chargement ────────────────────────────────────────────

    async def load(self) -> None:
        self._sm.transition("load")
        try:
            await self._do_load()
            self.mems(is_reload=False)
            self._sm.transition("ok")
            self._loaded_at = time.monotonic()
            logger.info(
                f"[{self.manifest.name}] ✅ chargé "
                f"(timeout={self.manifest.resources.timeout_seconds}s)"
            )
        except Exception as e:
            self._sm.transition("error")
            raise LoadError(f"[{self.manifest.name}] Échec chargement : {e}") from e

    async def _do_load(self) -> None:
        entry = self.manifest.plugin_dir / self.manifest.entry_point
        if not entry.exists():
            raise LoadError(f"Entry point introuvable : {entry}")

        src_dir = str(self.manifest.plugin_dir / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        module_name = f"xcore_plugin_{self.manifest.name}"
        self._module = self._import_module(module_name, entry)

        if not hasattr(self._module, "Plugin"):
            raise LoadError(f"Classe Plugin() manquante dans {entry}")

        cls = self._module.Plugin
        self._instance = self._instantiate(cls)

        if not isinstance(self._instance, BasePlugin):
            raise LoadError(
                f"Plugin ne respecte pas le contrat BasePlugin "
                f"(manque la méthode async handle(action, payload))"
            )

        # Injection du contexte riche
        ctx = PluginContext(
            name=self.manifest.name,
            services=self._services,
            events=self._events,
            hooks=self._hooks,
            env=self.manifest.env,
            config=getattr(self.manifest, "extra", {}),
        )
        if hasattr(self._instance, "_inject_context"):
            await self._instance._inject_context(ctx)
        elif hasattr(self._instance, "env_variable"):
            # rétro-compatibilité v1
            await self._instance.env_variable(self.manifest.env)

        if hasattr(self._instance, "on_load"):
            await self._instance.on_load()

        # Collecte le router HTTP custom si le plugin en expose un
        self._collect_router()

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
            raise LoadError(f"Impossible de créer le spec pour {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    # ── Appel ─────────────────────────────────────────────────

    async def call(self, action: str, payload: dict) -> dict:
        if self._instance is None:
            raise RuntimeError(f"[{self.manifest.name}] Plugin non chargé")

        self._sm.transition("call")
        timeout = self.manifest.resources.timeout_seconds
        try:
            result = await asyncio.wait_for(
                self._instance.handle(action, payload),
                timeout=timeout if timeout > 0 else None,
            )
            self._sm.transition("ok")
        except asyncio.TimeoutError:
            self._sm.transition("error")
            return {"status": "error", "msg": f"Timeout après {timeout}s", "code": "timeout"}
        except Exception as e:
            self._sm.transition("error")
            raise

        return result if isinstance(result, dict) else {"status": "ok", "result": result}

    # ── Reload ────────────────────────────────────────────────

    async def reload(self) -> None:
        self._sm.transition("reload")
        try:
            if hasattr(self._instance, "on_reload"):
                await self._instance.on_reload()
            await self._do_unload()
            await self._do_load()
            # is_reload=True : force la mise à jour des services existants
            self.mems(is_reload=True)
            self._sm.transition("ok")
            self._loaded_at = time.monotonic()
            logger.info(f"[{self.manifest.name}] 🔄 rechargé")
        except Exception as e:
            self._sm.transition("error")
            raise LoadError(f"[{self.manifest.name}] Échec reload : {e}") from e

    # ── Unload ────────────────────────────────────────────────

    async def unload(self) -> None:
        self._sm.transition("unload")
        try:
            await self._do_unload()
            self._sm.transition("ok")
            logger.info(f"[{self.manifest.name}] déchargé")
        except Exception as e:
            self._sm.transition("error")
            raise

    async def _do_unload(self) -> None:
        if self._instance and hasattr(self._instance, "on_unload"):
            await self._instance.on_unload()
        module_name = f"xcore_plugin_{self.manifest.name}"
        sys.modules.pop(module_name, None)
        src_dir = str(self.manifest.plugin_dir / "src")
        if src_dir in sys.path:
            sys.path.remove(src_dir)
        self._instance = None
        self._module   = None

    # ── Router HTTP custom ────────────────────────────────────

    def _collect_router(self) -> None:
        """
        Si le plugin expose get_router(), récupère l'APIRouter et le stocke.
        Le PluginLoader le collectera et le passera à Xcore pour montage sur l'app.
        """
        if self._instance is None:
            return
        get_router = getattr(self._instance, "get_router", None)
        if not callable(get_router):
            return
        try:
            router = get_router()
            if router is not None:
                self.plugin_router = router
                logger.info(
                    f"[{self.manifest.name}] 🌐 Router HTTP custom collecté "
                    f"({len(getattr(router, 'routes', []))} route(s))"
                )
        except Exception as e:
            logger.error(f"[{self.manifest.name}] get_router() erreur : {e}")

    # ── Propagation des services (fix #3 v1) ──────────────────

    def mems(self, *, is_reload: bool = False) -> dict:
        """
        Propage les services enregistrés par le plugin vers le container partagé.

        is_reload=False : n'ajoute que les nouvelles clés (respect ordre topo).
        is_reload=True  : écrase les clés du plugin rechargé (fix stale objects).
        """
        if self._instance is None:
            return self._services

        instance_services: dict = getattr(self._instance, "_services", {})

        if is_reload:
            if instance_services:
                self._services.update(instance_services)
                logger.info(
                    f"[{self.manifest.name}] 🔄 services mis à jour : "
                    f"{sorted(instance_services.keys())}"
                )
        else:
            new_keys = set(instance_services.keys()) - set(self._services.keys())
            if new_keys:
                for k in new_keys:
                    self._services[k] = instance_services[k]
                logger.info(
                    f"[{self.manifest.name}] 📦 nouveaux services : {sorted(new_keys)}"
                )

        return self._services

    # ── Status ────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "name":   self.manifest.name,
            "mode":   "trusted",
            "state":  self._sm.state.value,
            "loaded": self._instance is not None,
            "uptime": round(self.uptime, 1) if self.uptime else None,
        }
