"""Tests for PluginStateStore — table de vérité actif/inactif persistante."""

import json

from xcore.registry.state_store import PluginStateStore


class TestPluginStateStore:
    def test_default_enabled_when_never_toggled(self, tmp_path):
        store = PluginStateStore(tmp_path / ".xcore" / "plugins_state.json")
        assert store.is_enabled("shop") is True

    def test_set_enabled_false_then_true(self, tmp_path):
        path = tmp_path / ".xcore" / "plugins_state.json"
        store = PluginStateStore(path)

        store.set_enabled("shop", False, reason="maintenance")
        assert store.is_enabled("shop") is False
        assert store.all()["shop"]["reason"] == "maintenance"

        store.set_enabled("shop", True)
        assert store.is_enabled("shop") is True

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / ".xcore" / "plugins_state.json"
        PluginStateStore(path).set_enabled("shop", False)

        # Nouvelle instance (simule un redémarrage du process) : doit relire le fichier.
        reloaded = PluginStateStore(path)
        assert reloaded.is_enabled("shop") is False

    def test_writes_valid_json_atomically(self, tmp_path):
        path = tmp_path / ".xcore" / "plugins_state.json"
        store = PluginStateStore(path)
        store.set_enabled("shop", False)

        assert path.exists()
        assert not path.with_suffix(".json.tmp").exists()
        data = json.loads(path.read_text())
        assert data["shop"]["enabled"] is False

    def test_corrupt_file_starts_empty_instead_of_crashing(self, tmp_path):
        path = tmp_path / ".xcore" / "plugins_state.json"
        path.parent.mkdir(parents=True)
        path.write_text("{ not valid json")

        store = PluginStateStore(path)
        assert store.is_enabled("shop") is True
        assert store.all() == {}
