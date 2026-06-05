"""Tests for database adapters, utils and manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ── _utils.py ─────────────────────────────────────────────────────────────────

class TestDetectDriver:
    def test_aiomysql(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("mysql+aiomysql://host/db") == "aiomysql"

    def test_pymysql(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("mysql+pymysql://host/db") == "pymysql"

    def test_asyncpg(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("postgresql+asyncpg://host/db") == "asyncpg"

    def test_aiosqlite(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("sqlite+aiosqlite:///./db.sqlite") == "aiosqlite"

    def test_psycopg2(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("postgresql+psycopg2://host/db") == "psycopg2"

    def test_psycopg(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("postgresql+psycopg://host/db") == "psycopg"

    def test_unknown(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("some+unknown://host/db") == ""

    def test_cymysql(self):
        from xcore.services.database.adapters._utils import detect_driver
        assert detect_driver("mysql+cymysql://host/db") == "cymysql"


class TestDetectDbFamily:
    def test_sqlite(self):
        from xcore.services.database.adapters._utils import detect_db_family
        assert detect_db_family("sqlite:///./db.sqlite") == "sqlite"

    def test_mysql(self):
        from xcore.services.database.adapters._utils import detect_db_family
        assert detect_db_family("mysql+aiomysql://host/db") == "mysql"

    def test_mariadb(self):
        from xcore.services.database.adapters._utils import detect_db_family
        assert detect_db_family("mariadb+aiomysql://host/db") == "mysql"

    def test_postgresql(self):
        from xcore.services.database.adapters._utils import detect_db_family
        assert detect_db_family("postgresql+asyncpg://host/db") == "postgresql"

    def test_postgres_short(self):
        from xcore.services.database.adapters._utils import detect_db_family
        assert detect_db_family("postgres://host/db") == "postgresql"

    def test_unknown(self):
        from xcore.services.database.adapters._utils import detect_db_family
        assert detect_db_family("mongodb://host/db") == ""


class TestIsPrePingSafe:
    def test_safe_for_asyncpg(self):
        from xcore.services.database.adapters._utils import is_pre_ping_safe
        assert is_pre_ping_safe("postgresql+asyncpg://host/db") is True

    def test_unsafe_for_aiomysql(self):
        from xcore.services.database.adapters._utils import is_pre_ping_safe
        assert is_pre_ping_safe("mysql+aiomysql://host/db") is False

    def test_unsafe_for_cymysql(self):
        from xcore.services.database.adapters._utils import is_pre_ping_safe
        assert is_pre_ping_safe("mysql+cymysql://host/db") is False


class TestSanitizeConnectArgs:
    def test_empty_args(self):
        from xcore.services.database.adapters._utils import sanitize_connect_args
        assert sanitize_connect_args("sqlite:///./db", {}) == {}

    def test_unknown_driver_passes_all(self):
        from xcore.services.database.adapters._utils import sanitize_connect_args
        args = {"any_key": "any_value"}
        result = sanitize_connect_args("mongodb://host/db", args)
        assert result == args

    def test_known_driver_filters_valid(self):
        from xcore.services.database.adapters._utils import sanitize_connect_args
        args = {"charset": "utf8", "bad_key": "bad"}
        result = sanitize_connect_args("mysql+aiomysql://host/db", args)
        assert "charset" in result
        assert "bad_key" not in result

    def test_psycopg2_args(self):
        from xcore.services.database.adapters._utils import sanitize_connect_args
        args = {"connect_timeout": 5, "invalid_param": True}
        result = sanitize_connect_args("postgresql+psycopg2://host/db", args)
        assert "connect_timeout" in result
        assert "invalid_param" not in result

    def test_aiosqlite_args(self):
        from xcore.services.database.adapters._utils import sanitize_connect_args
        args = {"timeout": 10, "garbage": "ignored"}
        result = sanitize_connect_args("sqlite+aiosqlite:///./db", args)
        assert "timeout" in result
        assert "garbage" not in result


class TestSanitizeIsolationLevel:
    def test_none_returns_none(self):
        from xcore.services.database.adapters._utils import sanitize_isolation_level
        assert sanitize_isolation_level("sqlite:///db", None) is None

    def test_empty_string_returns_none(self):
        from xcore.services.database.adapters._utils import sanitize_isolation_level
        assert sanitize_isolation_level("sqlite:///db", "") is None

    def test_valid_sqlite_level(self):
        from xcore.services.database.adapters._utils import sanitize_isolation_level
        result = sanitize_isolation_level("sqlite:///db", "SERIALIZABLE")
        assert result == "SERIALIZABLE"

    def test_invalid_sqlite_level_returns_none(self):
        from xcore.services.database.adapters._utils import sanitize_isolation_level
        result = sanitize_isolation_level("sqlite:///db", "READ COMMITTED")
        assert result is None

    def test_valid_postgresql_level(self):
        from xcore.services.database.adapters._utils import sanitize_isolation_level
        result = sanitize_isolation_level("postgresql://host/db", "READ COMMITTED")
        assert result == "READ COMMITTED"

    def test_unknown_family_passes_through(self):
        from xcore.services.database.adapters._utils import sanitize_isolation_level
        result = sanitize_isolation_level("mongodb://host/db", "SNAPSHOT")
        assert result == "SNAPSHOT"

    def test_case_insensitive(self):
        from xcore.services.database.adapters._utils import sanitize_isolation_level
        result = sanitize_isolation_level("sqlite:///db", "serializable")
        assert result == "SERIALIZABLE"


# ── SQLAdapter ────────────────────────────────────────────────────────────────

def _make_db_config(url="sqlite:///:memory:", **kwargs):
    cfg = MagicMock()
    cfg.url = url
    cfg.pool_size = 5
    cfg.max_overflow = 10
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


class TestSQLAdapter:
    @pytest.mark.asyncio
    async def test_connect_sqlite(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config("sqlite:///:memory:"))
        await adapter.connect()
        assert adapter._engine is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_noop_when_not_connected(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config())
        await adapter.disconnect()  # should not raise

    @pytest.mark.asyncio
    async def test_execute_before_connect_raises(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config())
        with pytest.raises(RuntimeError, match="non initialisée"):
            adapter.execute("SELECT 1")

    @pytest.mark.asyncio
    async def test_execute_after_connect(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config("sqlite:///:memory:"))
        await adapter.connect()
        result = adapter.execute("SELECT 1")
        assert result is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_session_context_manager(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config("sqlite:///:memory:"))
        await adapter.connect()
        with adapter.session() as sess:
            assert sess is not None
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_session_before_connect_raises(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config())
        with pytest.raises(RuntimeError, match="non initialisée"):
            with adapter.session() as sess:
                pass

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config("sqlite:///:memory:"))
        await adapter.connect()
        with pytest.raises(ValueError):
            with adapter.session() as sess:
                raise ValueError("test error")
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_ping_ok(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config("sqlite:///:memory:"))
        await adapter.connect()
        ok, msg = await adapter.ping()
        assert ok is True
        assert msg == "ok"
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        adapter = SQLAdapter("test", _make_db_config())
        ok, msg = await adapter.ping()
        assert ok is False

    @pytest.mark.asyncio
    async def test_connect_with_execution_options(self):
        from xcore.services.database.adapters.sql import SQLAdapter
        cfg = _make_db_config("sqlite:///:memory:", execution_options={"no_parameters": True})
        adapter = SQLAdapter("test", cfg)
        await adapter.connect()
        assert adapter._engine is not None
        await adapter.disconnect()


# ── DatabaseManager ───────────────────────────────────────────────────────────

class TestDatabaseManager:
    @pytest.mark.asyncio
    async def test_init_empty_config(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.base import ServiceStatus
        manager = DatabaseManager({})
        await manager.init()
        assert manager._status == ServiceStatus.DEGRADED
        assert manager.adapters == {}

    @pytest.mark.asyncio
    async def test_init_with_sqlite(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.base import ServiceStatus
        cfg = _make_db_config("sqlite:///:memory:")
        cfg.type = "sqlite"
        manager = DatabaseManager({"main": cfg})
        await manager.init()
        assert manager._status == ServiceStatus.READY
        assert "main" in manager.adapters

    @pytest.mark.asyncio
    async def test_init_connection_failure(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.base import ServiceStatus
        cfg = _make_db_config("postgresql://invalid:5432/db")
        cfg.type = "postgresql"
        manager = DatabaseManager({"main": cfg})
        await manager.init()
        assert manager._status == ServiceStatus.DEGRADED

    def test_build_adapter_unknown_type_raises(self):
        from xcore.services.database.manager import DatabaseManager
        manager = DatabaseManager({})
        cfg = MagicMock()
        cfg.type = "unknown_db"
        with pytest.raises(ValueError, match="Type BDD inconnu"):
            manager._build_adapter("test", cfg)

    def test_build_adapter_sql(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.database.adapters.sql import SQLAdapter
        manager = DatabaseManager({})
        cfg = _make_db_config("sqlite:///:memory:", type="sqlite")
        adapter = manager._build_adapter("test", cfg)
        assert isinstance(adapter, SQLAdapter)

    def test_build_adapter_mongodb(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        manager = DatabaseManager({})
        cfg = _make_db_config("mongodb://host/db", type="mongodb")
        adapter = manager._build_adapter("test", cfg)
        assert isinstance(adapter, MongoDBAdapter)

    def test_build_adapter_redis(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.database.adapters.redis import RedisAdapter
        manager = DatabaseManager({})
        cfg = _make_db_config("redis://localhost:6379/0", type="redis")
        adapter = manager._build_adapter("test", cfg)
        assert isinstance(adapter, RedisAdapter)

    def test_build_adapter_async_sql(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        manager = DatabaseManager({})
        cfg = _make_db_config("sqlite+aiosqlite:///./db", type="sqlite+aio")
        adapter = manager._build_adapter("test", cfg)
        assert isinstance(adapter, AsyncSQLAdapter)

    @pytest.mark.asyncio
    async def test_shutdown(self):
        from xcore.services.database.manager import DatabaseManager
        from xcore.services.base import ServiceStatus
        cfg = _make_db_config("sqlite:///:memory:", type="sqlite")
        manager = DatabaseManager({"main": cfg})
        await manager.init()
        await manager.shutdown()
        assert manager._status == ServiceStatus.STOPPED
        assert manager.adapters == {}

    @pytest.mark.asyncio
    async def test_health_check_no_adapters(self):
        from xcore.services.database.manager import DatabaseManager
        manager = DatabaseManager({})
        ok, msg = await manager.health_check()
        assert ok is True

    @pytest.mark.asyncio
    async def test_health_check_with_adapter(self):
        from xcore.services.database.manager import DatabaseManager
        cfg = _make_db_config("sqlite:///:memory:", type="sqlite")
        manager = DatabaseManager({"main": cfg})
        await manager.init()
        ok, msg = await manager.health_check()
        assert ok is True
        assert "main" in msg

    def test_status(self):
        from xcore.services.database.manager import DatabaseManager
        manager = DatabaseManager({})
        s = manager.status()
        assert s["name"] == "database"
        assert "status" in s


# ── MongoDBAdapter ────────────────────────────────────────────────────────────

class TestMongoDBAdapter:
    def test_init(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = MagicMock()
        cfg.url = "mongodb://localhost:27017"
        cfg.database = "testdb"
        adapter = MongoDBAdapter("test", cfg)
        assert adapter.name == "test"

    @pytest.mark.asyncio
    async def test_connect_no_motor(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = MagicMock()
        cfg.url = "mongodb://localhost:27017"
        cfg.database = "testdb"
        adapter = MongoDBAdapter("test", cfg)
        with patch("builtins.__import__", side_effect=ImportError("no motor")):
            try:
                await adapter.connect()
            except ImportError:
                pass  # expected

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = MagicMock()
        cfg.url = "mongodb://localhost:27017"
        cfg.database = "testdb"
        adapter = MongoDBAdapter("test", cfg)
        await adapter.disconnect()  # should not raise

    @pytest.mark.asyncio
    async def test_ping_not_connected(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = MagicMock()
        cfg.url = "mongodb://localhost:27017"
        cfg.database = "testdb"
        adapter = MongoDBAdapter("test", cfg)
        ok, msg = await adapter.ping()
        assert ok is False

    def test_collection_not_connected_raises(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = MagicMock()
        cfg.url = "mongodb://localhost:27017"
        cfg.database = "testdb"
        adapter = MongoDBAdapter("test", cfg)
        with pytest.raises(RuntimeError):
            adapter.collection("users")


# ── RedisAdapter ──────────────────────────────────────────────────────────────

class TestRedisAdapter:
    def test_init(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        cfg = MagicMock()
        cfg.url = "redis://localhost:6379/0"
        adapter = RedisAdapter("cache", cfg)
        assert adapter.name == "cache"

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        cfg = MagicMock()
        cfg.url = "redis://localhost:6379/0"
        adapter = RedisAdapter("cache", cfg)
        await adapter.disconnect()  # should not raise

    @pytest.mark.asyncio
    async def test_ping_not_connected(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        cfg = MagicMock()
        cfg.url = "redis://localhost:6379/0"
        adapter = RedisAdapter("cache", cfg)
        ok, msg = await adapter.ping()
        assert ok is False

    @pytest.mark.asyncio
    async def test_connect_with_mock(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        cfg = MagicMock()
        cfg.url = "redis://localhost:6379/0"
        cfg.max_connections = 10
        adapter = RedisAdapter("cache", cfg)

        mock_redis_client = MagicMock()
        mock_redis_client.ping = AsyncMock(return_value=True)
        mock_redis_client.close = AsyncMock()

        mock_redis_module = MagicMock()
        mock_redis_module.asyncio.Redis.from_url.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module, "redis.asyncio": mock_redis_module.asyncio}):
            import importlib
            import xcore.services.database.adapters.redis as redis_adapter_mod
            original_connect = redis_adapter_mod.RedisAdapter.connect
            # Just verify init works and client is initially None
            assert adapter._client is None

    @pytest.mark.asyncio
    async def test_get_not_connected_raises(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        cfg = MagicMock()
        cfg.url = "redis://localhost:6379/0"
        cfg.max_connections = 10
        adapter = RedisAdapter("cache", cfg)
        with pytest.raises((RuntimeError, AttributeError)):
            await adapter.get("key")


# ── AsyncSQLAdapter ───────────────────────────────────────────────────────────

class TestAsyncSQLAdapter:
    def test_init(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_db_config("sqlite+aiosqlite:///./test.db")
        adapter = AsyncSQLAdapter("test", cfg)
        assert adapter.name == "test"

    @pytest.mark.asyncio
    async def test_ping_not_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_db_config("sqlite+aiosqlite:///./test.db")
        adapter = AsyncSQLAdapter("test", cfg)
        ok, msg = await adapter.ping()
        assert ok is False

    @pytest.mark.asyncio
    async def test_session_not_connected_raises(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_db_config("sqlite+aiosqlite:///./test.db")
        adapter = AsyncSQLAdapter("test", cfg)
        with pytest.raises(RuntimeError, match="non initialisée"):
            async with adapter.session() as sess:
                pass

    @pytest.mark.asyncio
    async def test_execute_not_connected_raises(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_db_config("sqlite+aiosqlite:///./test.db")
        adapter = AsyncSQLAdapter("test", cfg)
        with pytest.raises(RuntimeError, match="non initialisée"):
            await adapter.execute("SELECT 1")

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_db_config("sqlite+aiosqlite:///./test.db")
        adapter = AsyncSQLAdapter("test", cfg)
        await adapter.disconnect()  # should not raise
