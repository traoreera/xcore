"""#311 — contrat de services déclaré dans le manifeste, vérifié au chargement.

Vrai boot (PluginRegistry + ServiceContainer réels), vrais plugins sur disque.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from xcore import Xcore
from xcore.kernel.runtime import service_contracts as contracts
from xcore.kernel.security.validation import ManifestError, ManifestValidator
from xcore.sdk.plugin_base import ServiceProvision, ServiceRequirement

PROVIDER_SRC = """
from xcore.kernel.api.contract import TrustedBase, ok


class Writer:
    def write(self, doc):
        return {"written": doc}


class Plugin(TrustedBase):
    async def on_load(self):
        %s

    async def handle(self, action, payload):
        return ok()
"""

CONSUMER_SRC = """
from xcore.kernel.api.contract import TrustedBase, ok


class Plugin(TrustedBase):
    async def handle(self, action, payload):
        writer = self.get_service("doctype_writer")
        return ok(**writer.write(payload))
"""


def _plugin(root: Path, name: str, source: str, manifest: str = "") -> None:
    src = root / name / "src"
    src.mkdir(parents=True)
    (src / "main.py").write_text(textwrap.dedent(source))
    (root / name / "plugin.yaml").write_text(
        f"name: {name}\nversion: 1.0.0\nexecution_mode: trusted\n"
        'permissions:\n  - {resource: "*", actions: ["*"], effect: allow}\n'
        + textwrap.dedent(manifest)
    )


def provider(root: Path, version: str = "2.1", *, export: bool = True) -> None:
    body = 'self._services["doctype_writer"] = Writer()' if export else "pass"
    _plugin(
        root,
        "doctype",
        PROVIDER_SRC % body,
        f"""
        provides_services:
          - name: doctype_writer
            version: "{version}"
        """,
    )


def consumer(root: Path, name: str = "billing", constraint: str = ">=2") -> None:
    _plugin(
        root,
        name,
        CONSUMER_SRC,
        f"""
        requires_services:
          - name: doctype_writer
            version: "{constraint}"
        """,
    )


@pytest.fixture
def plugins_dir(tmp_path):
    root = tmp_path / "plugins"
    root.mkdir()
    return root


@pytest.fixture
async def boot(tmp_path, plugins_dir):
    apps: list[Xcore] = []

    async def _boot() -> Xcore:
        cfg = tmp_path / "integration.yaml"
        cfg.write_text(textwrap.dedent(f"""
            app:
              secret_key: test-secret-key-for-testing-min32chars
            plugins:
              directory: {plugins_dir}
              strict_trusted: false
              interval: 0
            services:
              scheduler:
                enabled: false
            """))
        app = Xcore(config_path=str(cfg))
        await app.boot()
        apps.append(app)
        return app

    yield _boot
    for app in apps:
        await app.shutdown()


def _loaded(app: Xcore) -> set[str]:
    # « xcore » : le handler noyau, toujours présent.
    return set(app.plugins._loader.all_names()) - {"xcore"}


def _refusals(caplog) -> dict[str, str]:
    return {
        r.xcore_ctx["plugin"]: r.xcore_ctx["reason"]
        for r in caplog.records
        if "service contract not satisfied" in r.getMessage()
    }


class TestLoadAll:
    async def test_satisfied_contract_loads_provider_first(self, boot, plugins_dir):
        # « billing » trie avant « doctype » et ne déclare aucun `requires` : seul le
        # contrat de services peut ordonner le chargement.
        consumer(plugins_dir)
        provider(plugins_dir)
        app = await boot()
        assert _loaded(app) == {"billing", "doctype"}
        result = await app.plugins.call("billing", "x", {"id": 1})
        assert result.get("written") == {"id": 1}, result

    async def test_missing_service_refuses_the_consumer(
        self, boot, plugins_dir, caplog
    ):
        consumer(plugins_dir)
        with caplog.at_level(logging.ERROR, logger="xcore.runtime.loader"):
            app = await boot()
        assert "billing" not in _loaded(app)
        assert "aucun plugin ne le fournit" in _refusals(caplog)["billing"]

    async def test_version_mismatch_names_both_plugins(self, boot, plugins_dir, caplog):
        provider(plugins_dir, version="1.4")
        consumer(plugins_dir, constraint=">=2")
        with caplog.at_level(logging.ERROR, logger="xcore.runtime.loader"):
            app = await boot()
        assert _loaded(app) == {"doctype"}
        reason = _refusals(caplog)["billing"]
        assert "'doctype'" in reason and "1.4" in reason and ">=2" in reason

    async def test_refused_provider_cascades_with_its_name(
        self, boot, plugins_dir, caplog
    ):
        provider(plugins_dir)
        # Le fournisseur requiert lui-même un service que personne ne fournit.
        manifest = plugins_dir / "doctype" / "plugin.yaml"
        manifest.write_text(manifest.read_text() + "requires_services: [vault]\n")
        consumer(plugins_dir)
        with caplog.at_level(logging.ERROR, logger="xcore.runtime.loader"):
            app = await boot()
        assert _loaded(app) == set()
        refusals = _refusals(caplog)
        assert "vault" in refusals["doctype"]
        assert "'doctype'" in refusals["billing"]

    async def test_provider_that_does_not_export_fails_and_cascades(
        self, boot, plugins_dir
    ):
        provider(plugins_dir, export=False)
        consumer(plugins_dir)
        app = await boot()
        assert _loaded(app) == set()

    async def test_core_service_satisfies_an_unversioned_requirement(
        self, boot, plugins_dir
    ):
        _plugin(plugins_dir, "reports", CONSUMER_SRC, "requires_services: [cache]\n")
        app = await boot()
        assert _loaded(app) == {"reports"}

    async def test_two_providers_of_one_service_second_is_refused(
        self, boot, plugins_dir, caplog
    ):
        provider(plugins_dir)
        _plugin(
            plugins_dir,
            "rival",
            PROVIDER_SRC % "pass",
            "provides_services: [doctype_writer]\n",
        )
        with caplog.at_level(logging.ERROR, logger="xcore.runtime.loader"):
            app = await boot()
        assert _loaded(app) == {"doctype"}
        assert "'doctype'" in _refusals(caplog)["rival"]

    async def test_plugins_without_contract_are_untouched(self, boot, plugins_dir):
        _plugin(plugins_dir, "plain", PROVIDER_SRC % "pass")
        app = await boot()
        assert _loaded(app) == {"plain"}


class TestSingleLoad:
    async def test_load_pulls_the_provider_from_disk(self, boot, plugins_dir):
        app = await boot()
        provider(plugins_dir)
        consumer(plugins_dir)
        await app.plugins.load("billing")
        assert _loaded(app) == {"billing", "doctype"}

    async def test_load_refuses_with_a_message_naming_both(self, boot, plugins_dir):
        provider(plugins_dir, version="1.0")
        app = await boot()
        consumer(plugins_dir, constraint=">=2")
        with pytest.raises(contracts.ServiceContractError) as exc:
            await app.plugins._loader.load("billing")
        assert "billing" in str(exc.value) and "'doctype'" in str(exc.value)
        assert "billing" not in _loaded(app)

    async def test_load_refuses_when_nobody_provides(self, boot, plugins_dir):
        app = await boot()
        consumer(plugins_dir)
        with pytest.raises(contracts.ServiceContractError, match="aucun plugin"):
            await app.plugins._loader.load("billing")

    async def test_reload_of_provider_reports_broken_consumers(
        self, boot, plugins_dir, caplog
    ):
        provider(plugins_dir, version="2.1")
        consumer(plugins_dir, constraint=">=2,<3")
        app = await boot()
        manifest = plugins_dir / "doctype" / "plugin.yaml"
        manifest.write_text(manifest.read_text().replace('"2.1"', '"3.0"'))
        loader = app.plugins._loader
        # Le manifeste d'un handler est relu au rechargement complet du plugin.
        await loader.unload("doctype")
        with caplog.at_level(logging.ERROR, logger="xcore.runtime.loader"):
            await loader.load("doctype")
            loader._warn_broken_consumers("doctype")
        broken = [
            r for r in caplog.records if "broken by provider reload" in r.getMessage()
        ]
        assert broken and broken[0].xcore_ctx["plugin"] == "billing"
        assert "3.0" in broken[0].xcore_ctx["reason"]


class TestManifestParsing:
    def _load(self, tmp_path, extra: str):
        _plugin(tmp_path, "p", PROVIDER_SRC % "pass", extra)
        return ManifestValidator().load_and_validate(tmp_path / "p")[0]

    def test_both_forms_are_accepted(self, tmp_path):
        manifest = self._load(
            tmp_path,
            """
            requires_services:
              - doctype_registry
              - name: doctype_writer
                version: ">=2"
            provides_services:
              - name: billing_api
                version: "1.2"
            """,
        )
        assert manifest.requires_services == [
            ServiceRequirement("doctype_registry"),
            ServiceRequirement("doctype_writer", ">=2"),
        ]
        assert manifest.provides_services == [ServiceProvision("billing_api", "1.2")]
        assert "requires_services" not in manifest.extra

    def test_default_is_no_contract(self, tmp_path):
        manifest = self._load(tmp_path, "")
        assert manifest.requires_services == [] and manifest.provides_services == []

    @pytest.mark.parametrize(
        "extra",
        [
            "requires_services: doctype_writer\n",
            "requires_services: [{version: '>=2'}]\n",
            "requires_services: [{name: a, version: 'soon'}]\n",
            "provides_services: [{name: a, version: 'latest'}]\n",
            "provides_services: [a, a]\n",
        ],
    )
    def test_malformed_contract_is_a_manifest_error(self, tmp_path, extra):
        with pytest.raises(ManifestError, match="Contrat de services"):
            self._load(tmp_path, extra)


class TestPureRules:
    def _m(self, name, requires=(), provides=()):
        return SimpleNamespace(
            name=name,
            requires_services=[ServiceRequirement.from_raw(r) for r in requires],
            provides_services=[ServiceProvision.from_raw(p) for p in provides],
        )

    def test_requirement_accepts(self):
        assert ServiceRequirement("s").accepts(None)
        assert ServiceRequirement("s", ">=2").accepts("2.1")
        assert not ServiceRequirement("s", ">=2").accepts("1.9")
        assert not ServiceRequirement("s", ">=2").accepts(None)

    def test_unversioned_registered_service_only_satisfies_star(self):
        consumer_ = self._m("c", requires=[{"name": "cache", "version": ">=1"}])
        reasons = contracts.unmet_requirements(consumer_, {}, available={"cache"})
        assert reasons and "sans version" in reasons[0]

    def test_self_requirement_is_ignored(self):
        m = self._m("p", requires=["svc"], provides=["svc"])
        providers, refused = contracts.refuse_unsatisfied([m])
        assert refused == {}
        assert contracts.service_dependencies(m, providers) == set()

    def test_dependencies_are_the_providers(self):
        a = self._m("a", provides=[{"name": "s", "version": "1.0"}])
        b = self._m("b", requires=["s", "cache"])
        providers, refused = contracts.refuse_unsatisfied([a, b], available={"cache"})
        assert refused == {}
        assert contracts.service_dependencies(b, providers) == {"a"}

    def test_missing_provisions(self):
        m = self._m("a", provides=["s", "t"])
        assert contracts.missing_provisions(m, {"s"}) == ["t"]
