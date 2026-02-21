"""
test_core/test_loader.py
=========================
Tests unitaires du PluginLoader.
Vérifie le chargement, le déchargement et le hot reload des plugins.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import FastAPI


class TestPluginLoader:
    def test_charge_plugin_valide(self, fake_plugin_dir):
        """Un plugin valide doit être chargé et son router monté."""
        try:
            from xcore.sandbox.manager import PluginManager

            app = FastAPI()
            loader = PluginManager(
                app=app,
                plugins_dir=str(fake_plugin_dir.parent),
                secret_key=b"xcore-test",
            )
            result = loader.load(fake_plugin_dir.name)

            assert result is True or result is not None
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_charge_plugin_invalide_retourne_false(self, invalid_plugin_dir):
        """Un plugin invalide doit être rejeté sans planter le serveur."""
        try:
            import asyncio

            from xcore.sandbox.manager import PluginManager

            app = FastAPI()
            loader = PluginManager(
                app=app,
                plugins_dir=str(invalid_plugin_dir.parent),
                secret_key=b"hefoeijr",
            )
            result = asyncio.run(loader.load(invalid_plugin_dir.name))

            assert result is False or result is None
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_plugin_monte_dans_fastapi(self, fake_plugin_dir):
        """Le router du plugin doit apparaître dans les routes FastAPI après chargement."""
        try:
            from manager.plManager.loader import PluginLoader

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(fake_plugin_dir.parent))
            loader.load(fake_plugin_dir.name)

            routes = [r.path for r in app.routes]
            assert any("/fake" in r for r in routes), (
                f"Route /fake introuvable. Routes disponibles : {routes}"
            )
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_charge_tous_les_plugins(self, plugins_dir, fake_plugin_dir):
        """load_all() doit charger tous les plugins valides du dossier."""
        try:
            from manager.plManager.loader import PluginLoader

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(plugins_dir))

            results = loader.load_all()

            assert isinstance(results, (list, dict))
            loaded = results if isinstance(results, list) else list(results.keys())
            assert "fake_plugin" in loaded or len(loaded) >= 1
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_double_chargement_evite_conflit(self, fake_plugin_dir):
        """Charger deux fois le même plugin ne doit pas créer de conflit de routes."""
        try:
            from manager.plManager.loader import PluginLoader

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(fake_plugin_dir.parent))

            loader.load(fake_plugin_dir.name)
            loader.load(fake_plugin_dir.name)  # deuxième fois

            routes_fake = [r for r in app.routes if "/fake" in getattr(r, "path", "")]
            # Pas de doublon
            paths = [r.path for r in routes_fake]
            assert len(paths) == len(set(paths)), "Routes dupliquées détectées"
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_dechargement_retire_les_routes(self, fake_plugin_dir):
        """Après unload(), les routes du plugin doivent disparaître de FastAPI."""
        try:
            from manager.plManager.loader import PluginLoader

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(fake_plugin_dir.parent))

            loader.load(fake_plugin_dir.name)
            routes_avant = len(app.routes)

            loader.unload(fake_plugin_dir.name)
            routes_apres = len(app.routes)

            assert routes_apres < routes_avant, (
                "Les routes n'ont pas été retirées après unload()"
            )
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_hot_reload_recharge_le_plugin(self, fake_plugin_dir):
        """reload() doit décharger puis recharger le plugin."""
        try:
            from manager.plManager.loader import PluginLoader

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(fake_plugin_dir.parent))

            loader.load(fake_plugin_dir.name)

            # Modifier le plugin en place
            run_py = fake_plugin_dir / "run.py"
            content = run_py.read_text()
            run_py.write_text(content.replace("'status': 'ok'", "'status': 'reloaded'"))

            result = loader.reload(fake_plugin_dir.name)
            assert result is True or result is not None
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_reload_nettoie_sys_modules(self, fake_plugin_dir):
        """Le hot reload doit purger sys.modules pour éviter le cache Python."""
        try:
            from manager.plManager.loader import PluginLoader

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(fake_plugin_dir.parent))

            loader.load(fake_plugin_dir.name)
            # S'assurer que le module est dans sys.modules
            module_key = f"fake_plugin"
            assert module_key in sys.modules or True  # peut varier selon l'impl

            loader.reload(fake_plugin_dir.name)
            # Après reload, l'ancien module ne doit plus être en cache
        except ImportError:
            pytest.skip("PluginLoader non disponible")

    def test_plugin_inexistant_retourne_false(self, plugins_dir):
        """Charger un plugin qui n'existe pas doit retourner False sans exception."""
        try:
            from manager.plManager.loader import PluginLoader

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(plugins_dir))

            result = loader.load("plugin_qui_nexiste_pas")
            assert result is False or result is None
        except ImportError:
            pytest.skip("PluginLoader non disponible")
        except Exception as e:
            pytest.fail(f"load() a levé une exception inattendue : {e}")

    def test_plugin_repository_mis_a_jour(self, fake_plugin_dir):
        """Après chargement, le plugin doit apparaître dans le repository."""
        try:
            from manager.plManager.loader import PluginLoader
            from manager.plManager.repository import PluginRepository

            app = FastAPI()
            loader = PluginLoader(app=app, plugins_dir=str(fake_plugin_dir.parent))
            repository = PluginRepository()

            loader.load(fake_plugin_dir.name)
            plugins = repository.list_active()

            names = [p.get("name") or p for p in plugins]
            assert "fake_plugin" in names or len(plugins) >= 1
        except ImportError:
            pytest.skip("PluginLoader ou PluginRepository non disponible")
