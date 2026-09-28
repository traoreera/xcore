"""
Integration tests — table de vérité persistante (enable/disable) + centre de
contrôle (registry_table). Vérifie que désactiver un plugin survit à un
redémarrage complet du process, pas seulement au unload en mémoire.
"""

import pytest

from xcore import Xcore


@pytest.fixture
def config_with_plugin(tmp_path):
    """Config xcore pointant vers un plugin de test réel sur disque."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()

    test_plugin = plugins_dir / "test_plugin"
    test_plugin.mkdir()
    src_dir = test_plugin / "src"
    src_dir.mkdir()

    (test_plugin / "plugin.yaml").write_text("""
name: test_plugin
version: 1.0.0
execution_mode: trusted
permissions:
  - resource: "*"
    actions: ["*"]
""")
    (src_dir / "main.py").write_text("""
from xcore.sdk import TrustedBase, ok

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        return ok(message="pong")
""")

    config_content = f"""
app:
  name: test-app
  secret_key: test-secret-key-32-chars-long!!!

plugins:
  directory: {plugins_dir}
  strict_trusted: false

services:
  databases: {{}}
  cache:
    backend: memory
    ttl: 300
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    return str(config_path)


class TestRegistryTable:
    @pytest.mark.asyncio
    async def test_loaded_plugin_appears_enabled_and_ready(self, config_with_plugin):
        xcore = Xcore(config_path=config_with_plugin)
        try:
            await xcore.boot()
            table = {row["name"]: row for row in xcore.plugins.registry_table()}
            assert table["test_plugin"]["enabled"] is True
            assert table["test_plugin"]["state"] == "ready"
            assert table["test_plugin"]["loaded"] is True
        finally:
            await xcore.shutdown()


class TestEnableDisable:
    @pytest.mark.asyncio
    async def test_disable_unloads_and_persists(self, config_with_plugin):
        xcore = Xcore(config_path=config_with_plugin)
        try:
            await xcore.boot()
            assert "test_plugin" in xcore.plugins.list_plugins()

            await xcore.plugins.disable("test_plugin", reason="maintenance")

            assert "test_plugin" not in xcore.plugins.list_plugins()
            table = {row["name"]: row for row in xcore.plugins.registry_table()}
            assert table["test_plugin"]["enabled"] is False
            assert table["test_plugin"]["state"] == "not_loaded"
            assert table["test_plugin"]["reason"] == "maintenance"
        finally:
            await xcore.shutdown()

    @pytest.mark.asyncio
    async def test_disabled_state_survives_restart(self, config_with_plugin):
        """Le cœur de la demande : désactiver doit tenir après un redémarrage du process."""
        first = Xcore(config_path=config_with_plugin)
        await first.boot()
        await first.plugins.disable("test_plugin")
        await first.shutdown()

        # Nouveau process xcore, même config/dossier de plugins.
        second = Xcore(config_path=config_with_plugin)
        try:
            await second.boot()
            assert "test_plugin" not in second.plugins.list_plugins()
            table = {row["name"]: row for row in second.plugins.registry_table()}
            assert table["test_plugin"]["enabled"] is False
            assert table["test_plugin"]["state"] == "not_loaded"
        finally:
            await second.shutdown()

    @pytest.mark.asyncio
    async def test_enable_reloads_plugin(self, config_with_plugin):
        xcore = Xcore(config_path=config_with_plugin)
        try:
            await xcore.boot()
            await xcore.plugins.disable("test_plugin")
            assert "test_plugin" not in xcore.plugins.list_plugins()

            await xcore.plugins.enable("test_plugin")

            assert "test_plugin" in xcore.plugins.list_plugins()
            table = {row["name"]: row for row in xcore.plugins.registry_table()}
            assert table["test_plugin"]["enabled"] is True
            assert table["test_plugin"]["state"] == "ready"
        finally:
            await xcore.shutdown()
