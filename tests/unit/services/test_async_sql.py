"""Tests for AsyncSQLAdapter with aiosqlite."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def _make_cfg(url="sqlite+aiosqlite:///", **kwargs):
    cfg = MagicMock()
    cfg.url = url
    cfg.echo = False
    cfg.pool_pre_ping = True
    cfg.pool_recycle = 1800
    cfg.pool_timeout = 30
    cfg.pool_reset_on_return = "rollback"
    cfg.connect_args = {}
    cfg.isolation_level = None
    cfg.execution_options = {}
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestAsyncSQLAdapter:
    @pytest.mark.asyncio
    async def test_connect_sqlite(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        await adapter.connect()
        assert adapter._engine is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        await adapter.disconnect()  # should not raise

    @pytest.mark.asyncio
    async def test_execute_not_connected_raises(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        with pytest.raises(RuntimeError, match="non initialisée"):
            await adapter.execute("SELECT 1")

    @pytest.mark.asyncio
    async def test_execute_after_connect(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        await adapter.connect()
        result = await adapter.execute("SELECT 1")
        assert result is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_ping_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        await adapter.connect()
        ok, msg = await adapter.ping()
        assert ok is True
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_ping_not_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        ok, msg = await adapter.ping()
        assert ok is False

    @pytest.mark.asyncio
    async def test_session_not_connected_raises(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        with pytest.raises(RuntimeError, match="non initialisée"):
            async with adapter.session():
                pass

    @pytest.mark.asyncio
    async def test_session_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        await adapter.connect()
        async with adapter.session() as sess:
            assert sess is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_engine_not_connected_raises(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        with pytest.raises(RuntimeError, match="non initialisée"):
            _ = adapter.engine

    @pytest.mark.asyncio
    async def test_engine_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        await adapter.connect()
        assert adapter.engine is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg())
        await adapter.connect()
        with pytest.raises(ValueError):
            async with adapter.session():
                raise ValueError("oops")
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connect_with_execution_options(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        adapter = AsyncSQLAdapter("test", _make_cfg(execution_options={"isolation_level": "AUTOCOMMIT"}))
        await adapter.connect()
        await adapter.disconnect()
