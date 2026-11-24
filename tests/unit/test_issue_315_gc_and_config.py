"""#315 — pause GC après un reload, clés de configuration inconnues, logging.enabled."""

from __future__ import annotations

import gc
import logging
import textwrap

import pytest

from xcore.configurations.loader import ConfigLoader, unknown_config_keys
from xcore.configurations.sections import LoggingConfig, XcoreConfig
from xcore.kernel.observability import configure_logging


class TestUnknownConfigKeys:
    def test_defaults_have_no_unknown_key(self):
        assert unknown_config_keys({}) == []

    def test_typo_in_a_section_is_reported_with_its_path(self):
        found = unknown_config_keys({"observability": {"logging": {"levle": "DEBUG"}}})
        assert found == [("observability.logging.levle", "clé inconnue")]

    def test_unknown_top_level_section(self):
        assert unknown_config_keys({"observabilty": {}}) == [
            ("observabilty", "clé inconnue")
        ]

    def test_named_databases_are_checked_one_by_one(self):
        raw = {"services": {"databases": {"main": {"url": "sqlite://", "ulr": "x"}}}}
        assert unknown_config_keys(raw) == [
            ("services.databases.main.ulr", "clé inconnue")
        ]

    def test_optional_section_is_descended(self):
        raw = {"services": {"celery": {"broker_url": "redis://", "nope": 1}}}
        assert unknown_config_keys(raw) == [("services.celery.nope", "clé inconnue")]

    def test_free_form_dicts_are_not_descended(self):
        raw = {
            "services": {
                "extensions": {"mail": {"anything": 1}},
                "databases": {"main": {"connect_args": {"whatever": 1}}},
                "scheduler": {"jobs": [{"id": "a", "func": "m:f", "hour": 3}]},
            },
            "plugins": {"snapshot": {"hidden": True, "custom": 1}},
            "security": {"rate_limit_default": {"calls": 1, "burst": 2}},
        }
        assert unknown_config_keys(raw) == []

    def test_app_dotenv_is_known(self):
        assert unknown_config_keys({"app": {"dotenv": ".env"}}) == []

    def test_plugins_tenancy_is_reported_as_ignored(self):
        found = unknown_config_keys({"plugins": {"tenancy": {"enabled": True}}})
        assert len(found) == 1
        assert found[0][0] == "plugins.tenancy"
        assert "tenancy" in found[0][1]

    def test_non_dict_section_does_not_crash(self):
        assert unknown_config_keys({"services": None, "middleware": []}) == []

    def test_every_documented_field_is_known(self):
        """Le contrôle se déduit des dataclasses : aucune liste de clés à tenir à la main."""
        from dataclasses import asdict

        raw = asdict(XcoreConfig())
        raw.pop("raw")
        raw["plugins"].pop("tenancy")
        assert unknown_config_keys(raw) == []

    def test_loader_warns_once_per_unknown_key(self, tmp_path, caplog):
        cfg = tmp_path / "integration.yaml"
        cfg.write_text(textwrap.dedent("""
            services:
              scheduler:
                pickle_protocol: 5
            """))
        with caplog.at_level(logging.WARNING, logger="xcore.config"):
            ConfigLoader.load(str(cfg))
        hits = [r for r in caplog.records if "clé sans effet" in r.getMessage()]
        assert len(hits) == 1
        assert hits[0].xcore_ctx["key"] == "services.scheduler.pickle_protocol"

    def test_a_failing_check_never_blocks_the_load(self, monkeypatch):
        import xcore.configurations.loader as loader

        def boom(raw):
            raise RuntimeError("x")

        monkeypatch.setattr(loader, "unknown_config_keys", boom)
        assert ConfigLoader._parse({}) is not None


class TestPreviouslyDroppedFields:
    """Champs présents dans les dataclasses mais que le loader ne lisait pas."""

    def test_fields_reach_the_config(self, tmp_path):
        cfg = tmp_path / "integration.yaml"
        cfg.write_text(textwrap.dedent("""
            plugins:
              gc_freeze_baseline: false
            services:
              scheduler:
                url: redis://example:6379/7
                misfire_grace_time: 5
            observability:
              logging:
                enabled: false
              tracing:
                max_local_spans: 12
            """))
        config = ConfigLoader.load(str(cfg))
        assert config.plugins.gc_freeze_baseline is False
        assert config.services.scheduler.url == "redis://example:6379/7"
        assert config.services.scheduler.misfire_grace_time == 5
        assert config.observability.logging.enabled is False
        assert config.observability.tracing.max_local_spans == 12


class TestLoggingEnabled:
    @pytest.fixture(autouse=True)
    def _restore(self):
        root = logging.getLogger("xcore")
        level, handlers = root.level, list(root.handlers)
        yield
        root.setLevel(level)
        root.handlers[:] = handlers

    def test_disabled_silences_every_xcore_logger(self):
        configure_logging(LoggingConfig(enabled=False, level="DEBUG"))
        assert not logging.getLogger("xcore.runtime.loader").isEnabledFor(
            logging.CRITICAL
        )

    def test_disabled_does_not_open_the_log_file(self, tmp_path):
        target = tmp_path / "app.log"
        configure_logging(LoggingConfig(enabled=False, file=str(target)))
        assert not target.exists()

    def test_enabled_again_restores_the_level(self):
        configure_logging(LoggingConfig(enabled=False))
        configure_logging(LoggingConfig(enabled=True, level="INFO"))
        assert logging.getLogger("xcore.anything").isEnabledFor(logging.INFO)


class TestGcFreezeBaseline:
    def _config(self, tmp_path, freeze: bool) -> str:
        plugins = tmp_path / "plugins"
        plugins.mkdir()
        cfg = tmp_path / "integration.yaml"
        cfg.write_text(textwrap.dedent(f"""
            plugins:
              directory: {plugins}
              gc_freeze_baseline: {str(freeze).lower()}
            services:
              scheduler:
                enabled: false
            """))
        return str(cfg)

    async def test_boot_freezes_and_shutdown_unfreezes(self, tmp_path):
        from xcore import Xcore

        gc.unfreeze()
        app = Xcore(config_path=self._config(tmp_path, True))
        await app.boot()
        try:
            assert gc.get_freeze_count() > 0
        finally:
            await app.shutdown()
        assert gc.get_freeze_count() == 0

    async def test_opt_out(self, tmp_path):
        from xcore import Xcore

        gc.unfreeze()
        app = Xcore(config_path=self._config(tmp_path, False))
        await app.boot()
        try:
            assert gc.get_freeze_count() == 0
        finally:
            await app.shutdown()

    async def test_objects_created_after_the_freeze_are_still_collected(self, tmp_path):
        """La raison d'être du contrôle de libération : un cycle né après le gel se libère."""
        import weakref

        from xcore import Xcore

        gc.unfreeze()
        app = Xcore(config_path=self._config(tmp_path, True))
        await app.boot()
        try:

            class Node:
                pass

            node = Node()
            node.me = node  # cycle : seul le collecteur cyclique peut le libérer
            ref = weakref.ref(node)
            del node
            gc.collect()
            assert ref() is None
        finally:
            await app.shutdown()
