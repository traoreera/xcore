"""
Depuis la 2.7.0 les dépendances propres à un backend (SQLAlchemy, Redis, Celery,
Alembic, drivers DB, prometheus-client) sont des extras optionnels : un simple
`pip install XCoreRuntime` ne les installe pas. `import xcore` et le boot
zero-config doivent donc fonctionner sans elles.

Ces tests simulent cette installation dans un sous-processus en bloquant les
paquets au niveau de l'import — l'environnement de dev, lui, les a tous.
(Régression : `xcore/sdk/__init__.py` importait SQLAlchemy à l'import, donc
`import xcore` plantait sur une installation minimale.)
"""

import subprocess
import sys
import textwrap

# `sys.modules[nom] = None` est l'idiome standard pour « ce paquet n'est pas
# installé » : `import nom` lève ModuleNotFoundError et `importlib.util.find_spec`
# renvoie None — exactement ce que voit le code sur une installation minimale.
BLOCKER = textwrap.dedent("""
    import sys

    for _name in (
        "sqlalchemy", "redis", "celery", "alembic", "aiosqlite", "psycopg2",
        "prometheus_client", "motor", "pymongo",
    ):
        sys.modules[_name] = None
    """)


def _run(code: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", BLOCKER + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=cwd,
    )


def test_import_xcore_works_without_optional_backends():
    result = _run("""
        import xcore
        import xcore.sdk as sdk
        from xcore import Xcore, TrustedBase
        from xcore.sdk import TrustedBase as T2, action, ok

        assert "BaseAsyncRepository" not in sdk.__all__
        assert "BaseSyncRepository" not in sdk.__all__
        exec("from xcore.sdk import *")   # ne doit pas lever
        print("import-ok")
        """)

    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout


def test_sql_adapters_raise_an_explicit_error_when_sqlalchemy_is_missing():
    result = _run("""
        import xcore.sdk as sdk
        try:
            sdk.BaseAsyncRepository
        except ImportError as e:
            print("ERR:", e)
        else:
            raise SystemExit("aurait dû lever ImportError")
        try:
            from xcore.sdk import BaseSyncRepository
        except ImportError as e:
            print("ERR2:", e)
        try:
            sdk.does_not_exist
        except AttributeError:
            print("attr-ok")
        """)

    assert result.returncode == 0, result.stderr
    assert "XCoreRuntime[db]" in result.stdout
    assert "ERR2:" in result.stdout
    assert "attr-ok" in result.stdout


def test_zero_config_boot_works_without_optional_backends(tmp_path):
    (tmp_path / "plugins").mkdir()
    (tmp_path / "integration.yaml").write_text(
        "app:\n  name: smoke\n  env: development\n  secret_key: smoke-key\n"
        "plugins:\n  directory: ./plugins\n  strict_trusted: false\n"
    )

    result = _run(
        """
        import asyncio
        from xcore import Xcore

        async def main():
            x = Xcore("integration.yaml")
            await x.boot()
            print("booted", x.plugins.list_plugins())
            await x.shutdown()

        asyncio.run(main())
        """,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "booted ['xcore']" in result.stdout


class TestWithSqlAlchemyInstalled:
    """Dans l'environnement de dev, rien ne change pour les utilisateurs de l'extra."""

    def test_adapters_resolve_lazily_and_are_cached(self):
        import xcore.sdk as sdk

        assert "BaseAsyncRepository" in sdk.__all__
        assert "BaseSyncRepository" in sdk.__all__
        first = sdk.BaseAsyncRepository
        assert first.__name__ == "BaseAsyncRepository"
        assert "BaseAsyncRepository" in vars(sdk)  # mis en cache
        assert sdk.BaseAsyncRepository is first

        from xcore.sdk import BaseSyncRepository

        assert BaseSyncRepository.__name__ == "BaseSyncRepository"

    def test_unknown_attribute_still_raises_attribute_error(self):
        import pytest

        import xcore.sdk as sdk

        with pytest.raises(AttributeError):
            sdk.definitely_not_there
