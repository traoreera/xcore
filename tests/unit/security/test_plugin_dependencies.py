"""#313 — dépendances d'un plugin : déclarées, et vérifiées."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from xcore.kernel.security import dependencies as deps
from xcore.kernel.security.dependencies import check_plugin_dependencies


def make_plugin(root: Path, name: str = "mail", **files: str) -> Path:
    plugin = root / name
    (plugin / "src").mkdir(parents=True)
    defaults = {"plugin.yaml": f"name: {name}\nversion: 1.0.0\n"}
    for rel, content in {**defaults, **files}.items():
        target = plugin / rel.replace("__", "/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content))
    return plugin


MAIN = "src__main.py"


class TestMissing:
    def test_the_case_of_the_issue(self, tmp_path):
        """Un plugin scelle des champs avec `cryptography` sans le déclarer."""
        plugin = make_plugin(
            tmp_path,
            **{
                MAIN: """
                import json
                from cryptography.fernet import Fernet
                from xcore import TrustedBase
                """,
                "pyproject.toml": '[project]\nname = "mail"\ndependencies = ["httpx"]\n',
            },
        )
        report = check_plugin_dependencies(plugin)
        assert not report.ok
        assert list(report.missing) == ["cryptography"]
        assert report.missing["cryptography"] == ["src/main.py:3"]
        assert report.sources == ["pyproject.toml"]
        assert "cryptography" in report.render()

    def test_lazy_import_inside_a_function_counts(self, tmp_path):
        plugin = make_plugin(
            tmp_path, **{MAIN: "def send():\n    import smtplib2_notreal\n"}
        )
        assert "smtplib2_notreal" in check_plugin_dependencies(plugin).missing

    def test_installed_package_suggests_its_distribution(self, tmp_path):
        plugin = make_plugin(tmp_path, **{MAIN: "import sqlalchemy\n"})
        report = check_plugin_dependencies(plugin)
        assert report.suggestions["sqlalchemy"] == ["sqlalchemy"]
        assert "déclarer : sqlalchemy" in report.render()

    def test_xcore_extras_are_not_provided_by_the_host(self, tmp_path):
        plugin = make_plugin(tmp_path, **{MAIN: "import redis\nimport celery\n"})
        assert set(check_plugin_dependencies(plugin).missing) == {"redis", "celery"}


class TestNotMissing:
    def test_stdlib_local_relative_and_xcore_are_ignored(self, tmp_path):
        plugin = make_plugin(
            tmp_path,
            **{
                MAIN: """
                import os, json
                from . import helpers
                from .models import Thing
                import helpers
                import services.mailer
                from xcore.sdk import cron
                """,
                "src__helpers.py": "",
                "src__services__mailer.py": "",
            },
        )
        assert check_plugin_dependencies(plugin).ok

    def test_host_core_dependencies_need_no_declaration(self, tmp_path):
        plugin = make_plugin(
            tmp_path,
            **{MAIN: "import fastapi, pydantic, yaml, starlette\nimport apscheduler\n"},
        )
        assert check_plugin_dependencies(plugin).ok

    def test_type_checking_block_is_ignored_but_its_else_is_not(self, tmp_path):
        plugin = make_plugin(
            tmp_path,
            **{MAIN: """
                from typing import TYPE_CHECKING
                if TYPE_CHECKING:
                    import only_for_types
                else:
                    import needed_at_runtime
                """},
        )
        assert list(check_plugin_dependencies(plugin).missing) == ["needed_at_runtime"]

    def test_import_guarded_by_import_error_is_optional(self, tmp_path):
        plugin = make_plugin(
            tmp_path,
            **{MAIN: """
                try:
                    import orjson_notreal
                except ImportError:
                    import fallback_notreal
                try:
                    import unguarded_notreal
                except ValueError:
                    pass
                """},
        )
        assert set(check_plugin_dependencies(plugin).missing) == {
            "fallback_notreal",
            "unguarded_notreal",
        }

    def test_non_shipped_folders_are_skipped(self, tmp_path):
        plugin = make_plugin(
            tmp_path,
            **{
                MAIN: "",
                "tests__test_x.py": "import pytest\n",
                "venv__lib__x.py": "import whatever_notreal\n",
                ".hidden__x.py": "import whatever_notreal\n",
            },
        )
        assert check_plugin_dependencies(plugin).ok

    def test_unreadable_file_is_reported_not_fatal(self, tmp_path):
        plugin = make_plugin(tmp_path, **{MAIN: "def broken(:\n"})
        report = check_plugin_dependencies(plugin)
        assert report.ok and report.unreadable == ["src/main.py"]


class TestDeclarations:
    @pytest.mark.parametrize(
        "files",
        [
            {
                "pyproject.toml": '[project]\ndependencies = ["SQLAlchemy[asyncio]>=2.1"]\n'
            },
            {
                "pyproject.toml": "[project]\n[project.optional-dependencies]\n"
                "db = [\"sqlalchemy ; python_version >= '3.12'\"]\n"
            },
            {
                "pyproject.toml": '[tool.poetry.dependencies]\npython = "^3.12"\nsqlalchemy = "^2"\n'
            },
            {"requirements.txt": "# base\n-r other.txt\nsqlalchemy==2.1.1  # orm\n"},
            {
                "plugin.yaml": "name: mail\nversion: 1.0.0\ndependencies:\n  - sqlalchemy>=2\n"
            },
        ],
        ids=["pep621", "extras", "poetry", "requirements", "manifest"],
    )
    def test_every_declaration_form_is_read(self, tmp_path, files):
        plugin = make_plugin(tmp_path, **{MAIN: "import sqlalchemy\n", **files})
        report = check_plugin_dependencies(plugin)
        assert report.ok, report.render()
        assert "sqlalchemy" in report.declared

    def test_module_name_differs_from_distribution_name(self, tmp_path):
        """`import yaml` est fourni par la distribution `pyyaml`."""
        plugin = make_plugin(
            tmp_path,
            **{MAIN: "import yaml\n", "requirements.txt": "PyYAML>=6\n"},
        )
        report = check_plugin_dependencies(plugin, provided=set())
        assert report.ok, report.render()

    def test_poetry_dev_group_does_not_count(self, tmp_path):
        plugin = make_plugin(
            tmp_path,
            **{
                MAIN: "import sqlalchemy\n",
                "pyproject.toml": '[tool.poetry.group.dev.dependencies]\nsqlalchemy = "*"\n',
            },
        )
        assert not check_plugin_dependencies(plugin).ok

    def test_manifest_dependencies_must_be_a_list(self, tmp_path):
        plugin = make_plugin(
            tmp_path,
            **{"plugin.yaml": "name: mail\nversion: 1.0.0\ndependencies: httpx\n"},
        )
        with pytest.raises(ValueError, match="liste"):
            check_plugin_dependencies(plugin)

    def test_json_manifest(self, tmp_path):
        plugin = make_plugin(tmp_path, **{MAIN: "import sqlalchemy\n"})
        (plugin / "plugin.yaml").unlink()
        (plugin / "plugin.json").write_text(
            json.dumps(
                {"name": "mail", "version": "1.0.0", "dependencies": ["sqlalchemy"]}
            )
        )
        report = check_plugin_dependencies(plugin)
        assert report.ok and report.sources == ["plugin.json"]

    def test_manifest_field_is_parsed_and_not_left_in_extra(self, tmp_path):
        from xcore.kernel.security.validation import ManifestValidator

        plugin = make_plugin(
            tmp_path,
            **{"plugin.yaml": "name: mail\nversion: 1.0.0\ndependencies: [httpx]\n"},
        )
        manifest = ManifestValidator().load_and_validate(plugin)[0]
        assert manifest.dependencies == ["httpx"]
        assert "dependencies" not in manifest.extra


class TestHelpers:
    def test_normalize_and_requirement_name(self):
        assert deps.normalize("Py_YAML.x") == "py-yaml-x"
        assert (
            deps.requirement_name("cryptography>=42 ; python_version<'4'")
            == "cryptography"
        )
        assert deps.requirement_name("  ") is None

    def test_host_provided_is_the_core_closure_without_extras(self):
        provided = deps.host_provided()
        assert {
            "fastapi",
            "starlette",
            "pydantic",
            "pyyaml",
            "xcoreruntime",
        } <= provided
        assert "sqlalchemy" not in provided and "celery" not in provided

    def test_missing_folder(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            check_plugin_dependencies(tmp_path / "nope")


class TestCommandLine:
    def test_exit_codes_and_output(self, tmp_path, capsys):
        good = make_plugin(tmp_path, "good", **{MAIN: "import json\n"})
        bad = make_plugin(tmp_path, "bad", **{MAIN: "import cryptography\n"})
        assert deps.main([str(good)]) == 0
        assert "good: ok" in capsys.readouterr().out
        assert deps.main([str(good), str(bad)]) == 1
        assert "bad: 1 dépendance" in capsys.readouterr().out

    def test_provided_option(self, tmp_path):
        bad = make_plugin(tmp_path, "bad", **{MAIN: "import cryptography\n"})
        assert deps.main([str(bad), "--provided", "cryptography"]) == 0

    def test_json_output(self, tmp_path, capsys):
        bad = make_plugin(tmp_path, "bad", **{MAIN: "import cryptography\n"})
        assert deps.main(["--json", str(bad)]) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["plugin"] == "bad" and payload[0]["ok"] is False
        assert "cryptography" in payload[0]["missing"]

    def test_missing_folder_is_exit_2(self, tmp_path, capsys):
        assert deps.main([str(tmp_path / "nope")]) == 2
        assert "not found" in capsys.readouterr().err

    def test_runs_as_a_module_in_ci(self, tmp_path):
        bad = make_plugin(tmp_path, "bad", **{MAIN: "import cryptography\n"})
        result = subprocess.run(
            [sys.executable, "-m", "xcore.kernel.security.dependencies", str(bad)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 1 and "cryptography" in result.stdout


class TestLoadTimeWarning:
    async def _boot(self, tmp_path, check: bool = True):
        from xcore import Xcore

        cfg = tmp_path / "integration.yaml"
        cfg.write_text(textwrap.dedent(f"""
            app:
              secret_key: test-secret-key-for-testing-min32chars
            plugins:
              directory: {tmp_path / "plugins"}
              strict_trusted: false
              interval: 0
              check_dependencies: {str(check).lower()}
            services:
              scheduler:
                enabled: false
            """))
        app = Xcore(config_path=str(cfg))
        await app.boot()
        await app.plugins._loader.wait_dependency_checks()
        return app

    def _plugin(self, tmp_path):
        make_plugin(
            tmp_path / "plugins",
            "mail",
            **{
                "plugin.yaml": "name: mail\nversion: 1.0.0\nexecution_mode: trusted\n",
                MAIN: """
                from xcore import TrustedBase, ok

                class Plugin(TrustedBase):
                    async def handle(self, action, payload):
                        import cryptography_notreal
                        return ok()
                """,
            },
        )

    async def test_loaded_plugin_with_undeclared_import_is_warned_not_refused(
        self, tmp_path, caplog
    ):
        self._plugin(tmp_path)
        with caplog.at_level(logging.WARNING, logger="xcore.runtime.loader"):
            app = await self._boot(tmp_path)
        try:
            assert "mail" in app.plugins._loader.all_names()
            hits = [
                r for r in caplog.records if "undeclared dependencies" in r.getMessage()
            ]
            assert len(hits) == 1
            assert hits[0].xcore_ctx["missing"] == ["cryptography_notreal"]
        finally:
            await app.shutdown()

    async def test_opt_out(self, tmp_path, caplog):
        self._plugin(tmp_path)
        with caplog.at_level(logging.WARNING, logger="xcore.runtime.loader"):
            app = await self._boot(tmp_path, check=False)
        try:
            assert not [r for r in caplog.records if "undeclared" in r.getMessage()]
        finally:
            await app.shutdown()
