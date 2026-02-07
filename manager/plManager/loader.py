import asyncio
import importlib
import json
import logging
import pathlib
import pkgutil
import sys
from typing import Any, Dict, List

from manager.plManager.installer import Installer
from manager.plManager.repository import Repository
from manager.plManager.validator import Validator
from manager.schemas.plugins import Plugin
from manager.tools.error import Error


class Loader(Repository):
    """Chargeur et exécuteur asynchrone des plugins (compatible FastAPI)"""

    def __init__(
        self,
        directory: str = "plugins",
        entry_point: str = "run",
        logger: logging.Logger | None = None,
        app: Any = None,
    ) -> None:
        super().__init__(logger=logger or logger)
        self.plugin_dir = pathlib.Path(directory)
        self.entry_point = entry_point
        self.active_plugins = self.get_all_active()
        self.validator = Validator()
        self.app = app

    # ------------------------------------------------------
    # 🔄 PURGE CACHE
    # ------------------------------------------------------

    def _purge_module_cache(self, base_name: str, dry_run: bool = False) -> None:
        relative_name = f"{self.plugin_dir}.{base_name}"
        to_remove = [
            m
            for m in list(sys.modules)
            if m.startswith(f"{self.plugin_dir.name}.{base_name}")
            and not m.startswith(f"{relative_name}.models")
        ]

        if dry_run:
            self.logger.info(f"[DryRun] Modules qui seraient purgés: {to_remove}")
            return

        for m in to_remove:
            del sys.modules[m]
        if to_remove:
            self.logger.debug(f"🧹 {len(to_remove)} modules purgés pour {base_name}")

    # ------------------------------------------------------
    # 🔍 DISCOVERY
    # ------------------------------------------------------
    def _discover_plugins(self) -> List[Dict[str, str]]:
        if not self.plugin_dir.exists():
            self.logger.warning(f"⚠️ Dossier introuvable: {self.plugin_dir}")
            return []

        discovered = []
        for _, name, _ in pkgutil.iter_modules([str(self.plugin_dir)]):
            discovered.append(
                {
                    "name": name,
                    "module": f"{self.plugin_dir.name}.{name}.{self.entry_point}",
                    "path": str(self.plugin_dir / name),
                }
            )
        return discovered

    # ------------------------------------------------------
    # 🔌 CHARGEMENT
    # ------------------------------------------------------
    def load_plugins(self) -> List[Any]:
        """Importe et initialise les plugins valides"""
        loaded_plugins = []

        # 🧹 Purge des plugins qui n'existent plus dans le dossier
        discovered_names = {p["name"] for p in self._discover_plugins()}
        active_names = {p["name"] for p in self.active_plugins}

        plugins_to_remove = active_names - discovered_names
        for plugin_name in plugins_to_remove:
            self.logger.info(f"🗑️ Suppression du plugin absent: {plugin_name}")
            self._purge_module_cache(plugin_name)
            # Retirer de la base de données
            self.disable(plugin_name)

        if plugins_to_remove:
            self.active_plugins = self.get_all_active()  # Rafraîchir la liste

        for plugin in self._discover_plugins():
            self._purge_module_cache(plugin["name"])
            mod = importlib.import_module(plugin["module"])

            # Validation / installation plugin
            if not any(p["name"] == plugin["name"] for p in self.active_plugins):
                self.add(
                    plugin=Plugin(
                        name=plugin["name"],
                        version=getattr(mod, "PLUGIN_INFO", {}).get(
                            "version", "unknown"
                        ),
                        author=getattr(mod, "PLUGIN_INFO", {}).get("author", "unknown"),
                        Api_prefix=getattr(mod, "PLUGIN_INFO", {}).get(
                            "Api_prefix", f"/app/{plugin['name']}"
                        ),
                        tag_for_identified=f"{getattr(mod, 'PLUGIN_INFO', {}).get('tag_for_identified', [])}",
                    )
                )
                loaded_plugins.append(mod)
                continue

            if not Validator()(mod):
                continue

            with open(f"{pathlib.Path(plugin['path'])}/plugin.json", "r") as f:
                plugin_data = f.read()
                data = json.loads(plugin_data)
            if rp := data.get("requirements", None):
                if not rp["isIstalled"]:
                    response = Installer()(
                        path=pathlib.Path(plugin["path"])
                    )  # TODO: threading this part
                    rp["isIstalled"] = True
                    with open(f"{pathlib.Path(plugin['path'])}/plugin.json", "w") as f:
                        f.write(json.dumps(data))

            loaded_plugins.append(mod)

        # 🔁 Intégration FastAPI
        if self.app:
            self._attach_plugins_to_app(loaded_plugins)

        return loaded_plugins

    # ------------------------------------------------------
    # ⚡ EXECUTION ASYNCHRONE
    # ------------------------------------------------------

    async def _run_plugin_async(self, mod: Any, app: Any = None) -> None:
        """Exécute la tâche du plugin en async si supporté"""
        instance = mod.Plugin()
        if asyncio.iscoroutinefunction(instance.concured):
            if hasattr(mod, "router") and app:
                app.include_router(mod.router)
            await instance.concured()
        else:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, instance.concured)
        self.logger.info(f"✅ Plugin {mod.__name__} exécuté")

    async def run_async_plugins(self, app: Any = None):
        """Exécute tous les plugins actifs en parallèle"""
        plugins = self.load_plugins()
        tasks = [self._run_plugin_async(mod, app) for mod in plugins]

        if not tasks:
            self.logger.warning("Aucun plugin actif à exécuter.")
            return

        await asyncio.gather(*tasks)
        self.logger.info("🚀 Tous les plugins exécutés.")

    # ------------------------------------------------------
    # 🧱 FERMETURE DB
    # ------------------------------------------------------
    def close_db(self):
        self.db.close_db()

    # ------------------------------------------------------
    # ⚙️ ATTACHEMENT AUTOMATIQUE AU CYCLE FASTAPI
    # ------------------------------------------------------

    def bind_to_fastapi(self) -> None:
        """Relie dynamiquement le chargeur au cycle de vie FastAPI."""
        if not self.app:
            self.logger.warning(
                "⚠️ Aucun app FastAPI détecté, impossible d'attacher le hook."
            )
            return

        @self.app.on_event("startup")
        async def _on_startup_reload_plugins() -> None:
            """Hook exécuté automatiquement au démarrage de FastAPI."""
            try:
                self.logger.info(
                    "🔄 Rechargement automatique des plugins au démarrage..."
                )
                loaded_plugins = self.load_plugins()

                # Attache tous les routers FastAPI
                for mod in loaded_plugins:
                    try:
                        if hasattr(mod, "router"):
                            self.app.include_router(mod.router)
                            self.logger.info(f"🔗 Plugin attaché : {mod.__name__}")
                    except Exception as e:
                        self.logger.error(
                            f"❌ Erreur include_router({mod.__name__}): {e}"
                        )

                # Forcer la mise à jour du schéma OpenAPI
                self.app.openapi_schema = None
                openapi = self.app.openapi()
                self.logger.debug(
                    f"✅ OpenAPI regénéré ({len(openapi.get('paths', {}))} routes)"
                )

                # Re-synchroniser la table des routes
                if hasattr(self.app.router, "routes"):
                    self.app.router.routes = list(self.app.routes)

                self.logger.info(
                    "✅ Routes FastAPI et Swagger synchronisées après startup."
                )

            except Exception as e:
                self.logger.error(
                    f"❌ Échec du rechargement des plugins au startup: {e}"
                )

    # ------------------------------------------------------
    # ⚡ INTÉGRATION FASTAPI
    # ------------------------------------------------------

    @staticmethod
    def _get_route_signature(route):
        """
        Génère une signature unique pour une route en gérant tous les types.

        Returns:
            tuple: (path, methods_tuple) où methods_tuple peut être:
                - tuple des méthodes HTTP pour les APIRoute
                - ('MOUNT',) pour les Mount
                - ('WEBSOCKET',) pour les WebSocketRoute
        """
        if not hasattr(route, "path"):
            return None

        path = route.path

        # Gestion des différents types de routes
        if hasattr(route, "methods"):
            # APIRoute classique
            methods = tuple(sorted(route.methods))
        elif route.__class__.__name__ == "Mount":
            # Mount pour fichiers statiques
            methods = ("MOUNT",)
        elif route.__class__.__name__ == "WebSocketRoute":
            # WebSocket
            methods = ("WEBSOCKET",)
        else:
            # Type inconnu, signature générique
            methods = (route.__class__.__name__,)

        return (path, methods)

    def _attach_plugins_to_app(self, loaded_plugins: list[Any]) -> None:
        """
        Attache dynamiquement les routers des plugins à l'application FastAPI.
        Gère les duplications et régénère OpenAPI.
        """
        if not self.app:
            return

        # --- 1️⃣ Sauvegarde des routes natives (FastAPI core) ---
        base_routes = list(self.app.routes)
        base_paths = {
            self._get_route_signature(r)
            for r in base_routes
            if self._get_route_signature(r) is not None
        }

        # --- 2️⃣ Purge des anciennes routes plugin ---
        before = len(self.app.routes)
        # Conserver uniquement les routes de base
        self.app.router.routes[:] = base_routes
        after = len(self.app.routes)
        if before != after:
            self.logger.debug(
                f"🧹 {before - after} anciennes routes plugin supprimées."
            )

        # --- 3️⃣ Inclusion sécurisée des nouveaux routers ---
        def _router_already_included(app, router):
            """Vérifie si un router est déjà inclus en comparant les signatures de routes."""
            existing_sigs = {
                self._get_route_signature(r)
                for r in app.routes
                if self._get_route_signature(r) is not None
            }
            router_sigs = {
                self._get_route_signature(r)
                for r in router.routes
                if self._get_route_signature(r) is not None
            }
            return router_sigs.issubset(existing_sigs)

        for mod in loaded_plugins:
            try:
                if hasattr(mod, "router"):
                    if not _router_already_included(self.app, mod.router):
                        self.app.include_router(mod.router)
                        self.logger.info(f"🔗 Plugin routes attachées : {mod.__name__}")
                    else:
                        self.logger.debug(f"ℹ️ Router déjà inclus : {mod.__name__}")
            except Exception as e:
                self.logger.error(f"❌ Erreur include_router pour {mod.__name__}: {e}")

        # --- 4️⃣ Régénération du schéma OpenAPI pour Swagger ---
        self.app.openapi_schema = None
        try:
            openapi = self.app.openapi()
            self.logger.debug(
                f"✅ OpenAPI regénéré ({len(openapi.get('paths', {}))} routes)"
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur régénération OpenAPI : {e}")

        # --- 5️⃣ Synchronisation complète du routeur FastAPI ---
        if hasattr(self.app.router, "routes"):
            self.app.router.routes[:] = list(self.app.routes)

        self.logger.info("✅ Routes FastAPI et Swagger synchronisées.")
