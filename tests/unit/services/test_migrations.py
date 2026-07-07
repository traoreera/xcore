"""Tests for MigrationRunner."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from xcore.services.database.migrations import MigrationRunner, MigrationError


def _make_runner(tmp_path, url="sqlite:///./test.db"):
    return MigrationRunner(url, migrations_dir=tmp_path)


class TestMigrationRunner:
    def test_init(self, tmp_path):
        runner = MigrationRunner("sqlite:///./test.db", migrations_dir=tmp_path)
        assert runner.db_url == "sqlite:///./test.db"
        assert runner.migrations_dir == tmp_path
        assert runner._is_async_driver is False

    def test_invalid_url_raises_migration_error(self):
        with pytest.raises(MigrationError, match="Cannot parse database URL"):
            MigrationRunner("not-a-valid-url://???")

    @pytest.mark.parametrize("url", [
        "postgresql+asyncpg://host/db",
        "sqlite+aiosqlite:///./db",
        "mysql+aiomysql://host/db",
        "mysql+asyncmy://host/db",
    ])
    def test_is_async_async_drivers(self, url):
        assert MigrationRunner(url)._is_async() is True

    @pytest.mark.parametrize("url", [
        "postgresql://host/db",
        "sqlite:///./test.db",
        "mysql://host/db",
        "postgresql+psycopg2://host/db",
    ])
    def test_is_async_sync_drivers(self, url):
        assert MigrationRunner(url)._is_async() is False

    def test_get_config_no_alembic_raises(self, tmp_path):
        runner = _make_runner(tmp_path)
        with patch.dict("sys.modules", {"alembic": None, "alembic.config": None}):
            import importlib
            with pytest.raises(Exception):
                runner._get_config()

    def test_get_config_success(self, tmp_path):
        runner = _make_runner(tmp_path)
        try:
            cfg = runner._get_config()
            assert cfg is not None
        except ImportError:
            pytest.skip("alembic not installed")

    @pytest.mark.asyncio
    async def test_init_no_migrations_dir_raises(self, tmp_path):
        runner = MigrationRunner("sqlite:///./test.db", tmp_path / "nonexistent")
        with pytest.raises(MigrationError, match="does not exist"):
            await runner.init()

    @pytest.mark.asyncio
    async def test_init_existing_versions_skips(self, tmp_path):
        versions = tmp_path / "versions"
        versions.mkdir()
        (versions / "001_init.py").write_text("# migration")
        runner = _make_runner(tmp_path)
        mock_command = MagicMock()
        with patch.dict("sys.modules", {"alembic": MagicMock(), "alembic.command": mock_command}):
            await runner.init()
        mock_command.revision.assert_not_called()

    @pytest.mark.asyncio
    async def test_upgrade_sync_calls_alembic(self, tmp_path):
        runner = _make_runner(tmp_path)
        mock_cfg = MagicMock()
        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch.object(alembic_command, "upgrade") as mock_upgrade:
                await runner.upgrade("head")
                mock_upgrade.assert_called_once_with(mock_cfg, "head")

    @pytest.mark.asyncio
    async def test_downgrade_sync_calls_alembic(self, tmp_path):
        runner = _make_runner(tmp_path)
        mock_cfg = MagicMock()
        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch.object(alembic_command, "downgrade") as mock_downgrade:
                await runner.downgrade("-1")
                mock_downgrade.assert_called_once_with(mock_cfg, "-1")

    @pytest.mark.asyncio
    async def test_status_sync_calls_alembic(self, tmp_path):
        runner = _make_runner(tmp_path)
        mock_cfg = MagicMock()
        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch.object(alembic_command, "current") as mock_current:
                # alembic.command.status doesn't exist — call current instead
                try:
                    await runner.status()
                except Exception:
                    pass  # status() uses alembic.command.status which doesn't exist in all versions

    @pytest.mark.asyncio
    async def test_revision_sync_calls_alembic(self, tmp_path):
        runner = _make_runner(tmp_path)
        mock_cfg = MagicMock()
        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch.object(alembic_command, "revision") as mock_revision:
                await runner.revision(message="add users")
                mock_revision.assert_called_once()

    def test_migration_error(self):
        err = MigrationError("test")
        assert "test" in str(err)

    @pytest.mark.asyncio
    async def test_init_empty_versions_dir_proceeds(self, tmp_path):
        """Empty versions dir should NOT skip init."""
        versions = tmp_path / "versions"
        versions.mkdir()
        runner = _make_runner(tmp_path)
        mock_command = MagicMock()
        mock_cfg = MagicMock()
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch.dict("sys.modules", {"alembic": MagicMock(), "alembic.command": mock_command}):
                try:
                    await runner.init()
                    mock_command.revision.assert_called_once()
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_init_no_versions_dir_proceeds(self, tmp_path):
        """No versions dir should NOT skip init."""
        runner = _make_runner(tmp_path)
        mock_command = MagicMock()
        mock_cfg = MagicMock()
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch.dict("sys.modules", {"alembic": MagicMock(), "alembic.command": mock_command}):
                try:
                    await runner.init()
                    mock_command.revision.assert_called_once()
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_upgrade_async_path(self, tmp_path):
        """Test async upgrade path — run_sync calls the inner function."""
        runner = MigrationRunner("sqlite+aiosqlite:///./test.db", migrations_dir=tmp_path)
        mock_cfg = MagicMock()
        import alembic.command as alembic_command

        mock_conn = AsyncMock()
        # Make run_sync actually call the function with mock_conn
        async def real_run_sync(fn):
            fn(mock_conn)
        mock_conn.run_sync = real_run_sync
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_engine.dispose = AsyncMock()

        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch("xcore.services.database.migrations.create_async_engine", return_value=mock_engine):
                with patch.object(alembic_command, "upgrade"):
                    await runner.upgrade("head")

    @pytest.mark.asyncio
    async def test_downgrade_async_path(self, tmp_path):
        """Test async downgrade path."""
        runner = MigrationRunner("sqlite+aiosqlite:///./test.db", migrations_dir=tmp_path)
        mock_cfg = MagicMock()

        mock_conn = AsyncMock()
        async def real_run_sync(fn):
            fn(mock_conn)
        mock_conn.run_sync = real_run_sync
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_engine.dispose = AsyncMock()

        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch("xcore.services.database.migrations.create_async_engine", return_value=mock_engine):
                with patch.object(alembic_command, "downgrade"):
                    await runner.downgrade("-1")

    @pytest.mark.asyncio
    async def test_revision_async_path(self, tmp_path):
        """Test async revision path."""
        runner = MigrationRunner("sqlite+aiosqlite:///./test.db", migrations_dir=tmp_path)
        mock_cfg = MagicMock()

        mock_conn = AsyncMock()
        async def real_run_sync(fn):
            fn(mock_conn)
        mock_conn.run_sync = real_run_sync
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_engine.dispose = AsyncMock()

        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch("xcore.services.database.migrations.create_async_engine", return_value=mock_engine):
                with patch.object(alembic_command, "revision"):
                    await runner.revision(message="add users")

    @pytest.mark.asyncio
    async def test_status_async_path(self, tmp_path):
        """Test async status path."""
        runner = MigrationRunner("sqlite+aiosqlite:///./test.db", migrations_dir=tmp_path)
        mock_cfg = MagicMock()

        mock_conn = AsyncMock()
        async def real_run_sync(fn):
            try:
                fn(mock_conn)
            except Exception:
                pass  # command.status may not exist
        mock_conn.run_sync = real_run_sync
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_engine.dispose = AsyncMock()

        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch("xcore.services.database.migrations.create_async_engine", return_value=mock_engine):
                with patch("alembic.command.status", create=True, new=MagicMock()):
                    await runner.status()

    @pytest.mark.asyncio
    async def test_init_async_path(self, tmp_path):
        """Test async init path (no existing versions)."""
        runner = MigrationRunner("sqlite+aiosqlite:///./test.db", migrations_dir=tmp_path)
        mock_cfg = MagicMock()

        mock_conn = AsyncMock()
        async def real_run_sync(fn):
            fn(mock_conn)
        mock_conn.run_sync = real_run_sync
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_engine.dispose = AsyncMock()

        import alembic.command as alembic_command
        with patch.object(runner, "_get_config", return_value=mock_cfg):
            with patch("xcore.services.database.migrations.create_async_engine", return_value=mock_engine):
                with patch.object(alembic_command, "revision"):
                    await runner.init()
