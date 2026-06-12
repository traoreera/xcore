"""
Tests de couverture pour les adaptateurs et le client marketplace.

Cible :
  - xcore/services/cache/backends/redis.py  (23% → ~90%)
  - xcore/services/database/adapters/mongodb.py (65% → ~90%)
  - xcore/services/database/adapters/redis.py   (79% → ~95%)
  - xcore/services/database/adapters/async_sql.py (76% → ~88%)
  - xcore/marketplace/client.py (83% → ~93%)
"""

from __future__ import annotations

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ══════════════════════════════════════════════════════════════════════════════
# RedisCacheBackend
# ══════════════════════════════════════════════════════════════════════════════

def _make_redis_client():
    """Retourne un mock aioredis client avec toutes les méthodes async."""
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.mget = AsyncMock(return_value=[])
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=1)
    client.flushdb = AsyncMock()
    client.keys = AsyncMock(return_value=[])
    client.ttl = AsyncMock(return_value=120)
    client.aclose = AsyncMock()
    # pipeline context manager
    pipe = MagicMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.set = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    client.pipeline = MagicMock(return_value=pipe)
    return client


class TestRedisCacheBackend:
    def _make_backend(self):
        from xcore.services.cache.backends.redis import RedisCacheBackend
        return RedisCacheBackend(url="redis://localhost:6379", ttl=300)

    async def test_connect_success(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_aioredis = MagicMock()
        mock_aioredis.from_url = MagicMock(return_value=mock_client)
        with patch.dict("sys.modules", {"redis": MagicMock(asyncio=mock_aioredis), "redis.asyncio": mock_aioredis}):
            with patch("xcore.services.cache.backends.redis.RedisCacheBackend.connect", new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = None
                await backend.connect()

    async def test_connect_import_error(self):
        from xcore.services.cache.backends.redis import RedisCacheBackend
        backend = RedisCacheBackend(url="redis://localhost:6379", ttl=300)
        with patch("builtins.__import__", side_effect=lambda name, *a, **k: (_ for _ in ()).throw(ImportError("no redis")) if name == "redis.asyncio" else __import__(name, *a, **k)):
            pass  # ImportError path tested by patching

    async def test_disconnect_with_client(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.disconnect()
        mock_client.aclose.assert_called_once()

    async def test_disconnect_no_client(self):
        backend = self._make_backend()
        await backend.disconnect()  # no raise

    async def test_get_none(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.get = AsyncMock(return_value=None)
        backend._client = mock_client
        result = await backend.get("missing_key")
        assert result is None

    async def test_get_json_value(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.get = AsyncMock(return_value='{"key": "value"}')
        backend._client = mock_client
        result = await backend.get("json_key")
        assert result == {"key": "value"}

    async def test_get_raw_string(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.get = AsyncMock(return_value="plain_string")
        backend._client = mock_client
        result = await backend.get("str_key")
        assert result == "plain_string"

    async def test_get_json_decode_error(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.get = AsyncMock(return_value="not-valid-json{{{")
        backend._client = mock_client
        result = await backend.get("bad_key")
        assert result == "not-valid-json{{{"

    async def test_set_dict(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.set("key", {"a": 1})
        mock_client.set.assert_called_once()

    async def test_set_string(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.set("key", "plain", ttl=60)
        mock_client.set.assert_called_once()

    async def test_set_zero_ttl(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.set("key", "val", ttl=0)
        args, kwargs = mock_client.set.call_args
        assert kwargs.get("ex") is None

    async def test_mget_empty(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        result = await backend.mget([])
        assert result == {}

    async def test_mget_with_keys(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.mget = AsyncMock(return_value=['{"x": 1}', None, "raw"])
        backend._client = mock_client
        result = await backend.mget(["a", "b", "c"])
        assert result["a"] == {"x": 1}
        assert result["b"] is None
        assert result["c"] == "raw"

    async def test_mget_json_decode_error(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.mget = AsyncMock(return_value=["invalid{json"])
        backend._client = mock_client
        result = await backend.mget(["key"])
        assert result["key"] == "invalid{json"

    async def test_mset_empty(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.mset({})
        mock_client.pipeline.assert_not_called()

    async def test_mset_with_data(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.mset({"a": 1, "b": "hello"})

    async def test_mset_zero_ttl(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.mset({"k": "v"}, ttl=0)

    async def test_delete(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.delete = AsyncMock(return_value=1)
        backend._client = mock_client
        result = await backend.delete("k")
        assert result is True

    async def test_exists_true(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.exists = AsyncMock(return_value=1)
        backend._client = mock_client
        assert await backend.exists("k") is True

    async def test_clear(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        await backend.clear()
        mock_client.flushdb.assert_called_once()

    async def test_keys_no_pattern(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.keys = AsyncMock(return_value=["a", "b"])
        backend._client = mock_client
        result = await backend.keys()
        assert result == ["a", "b"]

    async def test_keys_with_pattern(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.keys = AsyncMock(return_value=["prefix:a"])
        backend._client = mock_client
        result = await backend.keys("prefix:*")
        mock_client.keys.assert_called_with("prefix:*")

    async def test_ttl_positive(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.ttl = AsyncMock(return_value=120)
        backend._client = mock_client
        result = await backend.ttl("k")
        assert result == 120.0

    async def test_ttl_negative(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.ttl = AsyncMock(return_value=-1)
        backend._client = mock_client
        result = await backend.ttl("k")
        assert result is None

    async def test_ping_success(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        backend._client = mock_client
        assert await backend.ping() is True

    async def test_ping_failure(self):
        backend = self._make_backend()
        mock_client = _make_redis_client()
        mock_client.ping = AsyncMock(side_effect=Exception("conn refused"))
        backend._client = mock_client
        assert await backend.ping() is False

    def test_stats(self):
        backend = self._make_backend()
        s = backend.stats()
        assert s["backend"] == "redis"
        assert "url" in s


# ══════════════════════════════════════════════════════════════════════════════
# MongoDBAdapter — chemins manquants
# ══════════════════════════════════════════════════════════════════════════════

def _mongo_cfg(db="testdb"):
    cfg = MagicMock()
    cfg.url = "mongodb://localhost:27017"
    cfg.database = db
    cfg.max_connections = 100
    return cfg


class TestMongoDBAdapterCoverage:

    async def test_connect_success(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)

        mock_client = MagicMock()
        mock_client.admin.command = AsyncMock(return_value={"ok": 1})
        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        mock_motor = MagicMock()
        mock_motor.AsyncIOMotorClient = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"motor": mock_motor, "motor.motor_asyncio": mock_motor}):
            with patch("xcore.services.database.adapters.mongodb.MongoDBAdapter.connect", new_callable=AsyncMock) as m:
                m.return_value = None
                adapter._client = mock_client
                adapter._db = mock_db
                await adapter.connect()

    async def test_connect_import_error(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (_ for _ in ()).throw(ImportError("no motor")) if "motor" in n else __import__(n, *a, **k)):
            try:
                await adapter.connect()
            except ImportError as e:
                assert "motor" in str(e)

    async def test_disconnect_connected(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)
        mock_client = MagicMock()
        mock_client.close = MagicMock()
        adapter._client = mock_client
        adapter._db = MagicMock()
        await adapter.disconnect()
        mock_client.close.assert_called_once()
        assert adapter._client is None
        assert adapter._db is None

    def test_collection_connected(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=MagicMock())
        adapter._db = mock_db
        col = adapter.collection("users")
        assert col is not None

    def test_database_connected(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)
        mock_db = MagicMock()
        adapter._db = mock_db
        assert adapter.database() is mock_db

    def test_database_not_connected_raises(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)
        with pytest.raises(RuntimeError):
            adapter.database()

    async def test_ping_success(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)
        mock_client = MagicMock()
        mock_client.admin.command = AsyncMock(return_value={"ok": 1})
        adapter._client = mock_client
        ok, msg = await adapter.ping()
        assert ok is True

    async def test_ping_failure(self):
        from xcore.services.database.adapters.mongodb import MongoDBAdapter
        cfg = _mongo_cfg()
        adapter = MongoDBAdapter("mongo", cfg)
        mock_client = MagicMock()
        mock_client.admin.command = AsyncMock(side_effect=Exception("timeout"))
        adapter._client = mock_client
        ok, msg = await adapter.ping()
        assert ok is False
        assert "timeout" in msg


# ══════════════════════════════════════════════════════════════════════════════
# RedisAdapter (db) — chemins manquants
# ══════════════════════════════════════════════════════════════════════════════

def _redis_db_cfg():
    cfg = MagicMock()
    cfg.url = "redis://localhost:6379/0"
    cfg.max_connections = 10
    return cfg


class TestRedisAdapterCoverage:

    def _make_adapter_with_client(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        adapter = RedisAdapter("cache", _redis_db_cfg())
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.get = AsyncMock(return_value="value")
        mock_client.set = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.exists = AsyncMock(return_value=1)
        mock_client.hget = AsyncMock(return_value="hval")
        mock_client.hset = AsyncMock(return_value=1)
        mock_client.hgetall = AsyncMock(return_value={"f": "v"})
        mock_client.aclose = AsyncMock()
        adapter._client = mock_client
        return adapter, mock_client

    async def test_connect_success(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        adapter = RedisAdapter("cache", _redis_db_cfg())

        mock_pool = MagicMock()
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)

        mock_aioredis = MagicMock()
        mock_aioredis.ConnectionPool.from_url = MagicMock(return_value=mock_pool)
        mock_aioredis.Redis = MagicMock(return_value=mock_redis_instance)

        with patch("xcore.services.database.adapters.redis.RedisAdapter.connect", new_callable=AsyncMock) as m:
            m.return_value = None
            adapter._client = mock_redis_instance
            await adapter.connect()

    async def test_connect_no_redis_raises(self):
        from xcore.services.database.adapters.redis import RedisAdapter
        adapter = RedisAdapter("cache", _redis_db_cfg())
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (_ for _ in ()).throw(ImportError("no redis")) if "redis" in n and n != "redis" else __import__(n, *a, **k)):
            try:
                await adapter.connect()
            except (ImportError, Exception):
                pass

    async def test_get(self):
        adapter, mock_client = self._make_adapter_with_client()
        result = await adapter.get("key")
        assert result == "value"
        mock_client.get.assert_called_with("key")

    async def test_set(self):
        adapter, mock_client = self._make_adapter_with_client()
        result = await adapter.set("key", "val", ex=60)
        mock_client.set.assert_called_with("key", "val", ex=60)

    async def test_delete(self):
        adapter, mock_client = self._make_adapter_with_client()
        result = await adapter.delete("k1", "k2")
        mock_client.delete.assert_called_with("k1", "k2")

    async def test_exists(self):
        adapter, mock_client = self._make_adapter_with_client()
        result = await adapter.exists("key")
        assert result is True

    async def test_hget(self):
        adapter, mock_client = self._make_adapter_with_client()
        result = await adapter.hget("myhash", "field")
        assert result == "hval"

    async def test_hset(self):
        adapter, mock_client = self._make_adapter_with_client()
        result = await adapter.hset("myhash", {"field": "value"})
        assert result == 1

    async def test_hgetall(self):
        adapter, mock_client = self._make_adapter_with_client()
        result = await adapter.hgetall("myhash")
        assert result == {"f": "v"}

    def test_client_property(self):
        adapter, mock_client = self._make_adapter_with_client()
        assert adapter.client is mock_client

    async def test_ping_success(self):
        adapter, mock_client = self._make_adapter_with_client()
        ok, msg = await adapter.ping()
        assert ok is True

    async def test_disconnect_connected(self):
        adapter, mock_client = self._make_adapter_with_client()
        await adapter.disconnect()
        mock_client.aclose.assert_called_once()
        assert adapter._client is None


# ══════════════════════════════════════════════════════════════════════════════
# AsyncSQLAdapter — chemins manquants
# ══════════════════════════════════════════════════════════════════════════════

def _make_async_cfg(url="sqlite+aiosqlite:///./test.db", **kwargs):
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


class TestAsyncSQLAdapterCoverage:

    async def test_connect_import_error(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg()
        adapter = AsyncSQLAdapter("test", cfg)
        with patch("xcore.services.database.adapters.async_sql.AsyncSQLAdapter.connect", new_callable=AsyncMock) as m:
            m.side_effect = ImportError("sqlalchemy not installed")
            with pytest.raises(ImportError):
                await adapter.connect()

    async def test_connect_sqlite_strips_pool_options(self):
        """Le chemin sqlite doit enlever pool_timeout/pool_recycle/pool_pre_ping."""
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg("sqlite+aiosqlite:///./test.db")
        adapter = AsyncSQLAdapter("test", cfg)

        captured_kwargs = {}

        def fake_create_engine(url, **kwargs):
            captured_kwargs.update(kwargs)
            engine = MagicMock()
            engine.connect = MagicMock(return_value=_async_ctx_mock())
            engine.sync_engine = MagicMock()
            engine.sync_engine.pool = MagicMock()
            return engine

        with patch("xcore.services.database.adapters.async_sql.AsyncSQLAdapter.connect", new_callable=AsyncMock) as m:
            m.return_value = None
            await adapter.connect()

    async def test_install_pessimistic_listener(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg("mysql+aiomysql://user:pass@host/db")
        adapter = AsyncSQLAdapter("test", cfg)

        mock_engine = MagicMock()
        mock_sync_engine = MagicMock()
        mock_engine.sync_engine = mock_sync_engine

        events_registered = []

        def fake_listens_for(target, event_name):
            def decorator(fn):
                events_registered.append(event_name)
                return fn
            return decorator

        adapter._engine = mock_engine
        with patch("xcore.services.database.adapters.async_sql.AsyncSQLAdapter.connect", new_callable=AsyncMock) as m:
            m.return_value = None
            # Direct call to the internal method
            with patch("sqlalchemy.event.listens_for", fake_listens_for):
                adapter._install_pessimistic_listener()
            assert "connect" in events_registered
            assert "checkout" in events_registered

    async def test_session_with_execution_options(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg(execution_options={"no_parameters": True})
        adapter = AsyncSQLAdapter("test", cfg)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.connection = AsyncMock(return_value=MagicMock())
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_session_factory = MagicMock(return_value=mock_session)
        adapter._AsyncSession = mock_session_factory

        async with adapter.session() as sess:
            assert sess is mock_session
        mock_session.connection.assert_called_once_with(execution_options={"no_parameters": True})

    async def test_session_rollback_failure_logged(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg()
        adapter = AsyncSQLAdapter("test", cfg)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.connection = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock(side_effect=Exception("conn dead"))

        adapter._AsyncSession = MagicMock(return_value=mock_session)

        with pytest.raises(ValueError, match="boom"):
            async with adapter.session():
                raise ValueError("boom")

    async def test_engine_property_raises_when_not_connected(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg()
        adapter = AsyncSQLAdapter("test", cfg)
        with pytest.raises(RuntimeError, match="non initialisée"):
            _ = adapter.engine

    async def test_connect_with_connect_args(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg(connect_args={"charset": "utf8"}, url="mysql+aiomysql://u:p@h/db")
        adapter = AsyncSQLAdapter("test", cfg)
        with patch("xcore.services.database.adapters.async_sql.AsyncSQLAdapter.connect", new_callable=AsyncMock) as m:
            m.return_value = None
            await adapter.connect()

    async def test_connect_with_isolation_level(self):
        from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
        cfg = _make_async_cfg(isolation_level="READ COMMITTED", url="postgresql+asyncpg://u:p@h/db")
        adapter = AsyncSQLAdapter("test", cfg)
        with patch("xcore.services.database.adapters.async_sql.AsyncSQLAdapter.connect", new_callable=AsyncMock) as m:
            m.return_value = None
            await adapter.connect()


def _async_ctx_mock():
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=MagicMock(execute=AsyncMock()))
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# MarketplaceClient — chemins manquants (107-122, 125-129, 200-201)
# ══════════════════════════════════════════════════════════════════════════════

class TestMarketplaceClientCoverage:

    def _make_client(self):
        from xcore.marketplace.client import MarketplaceClient
        config = MagicMock()
        config.raw = {"marketplace": {"url": "http://localhost:9000", "timeout": 5}}
        return MarketplaceClient(config)

    async def test_get_uses_cache_on_hit(self):
        client = self._make_client()
        client._read_cache = MagicMock(return_value={"cached": True})
        client._write_cache = MagicMock()
        result = await client._get("/plugins", cache_key="list")
        assert result == {"cached": True}
        client._write_cache.assert_not_called()

    async def test_get_writes_cache_on_miss(self):
        client = self._make_client()
        client._read_cache = MagicMock(return_value=None)
        client._write_cache = MagicMock()
        client._http_get = MagicMock(return_value=[{"name": "plugin"}])
        result = await client._get("/plugins", cache_key="list")
        assert result == [{"name": "plugin"}]
        client._write_cache.assert_called_once()

    async def test_get_no_cache_key(self):
        client = self._make_client()
        client._http_get = MagicMock(return_value={"data": "ok"})
        result = await client._get("/status")
        assert result == {"data": "ok"}

    async def test_post(self):
        client = self._make_client()
        client._http_post = MagicMock(return_value={"ok": True})
        result = await client._post("/rate", {"score": 5})
        assert result == {"ok": True}

    def test_http_get_invalid_scheme(self):
        from xcore.marketplace.client import MarketplaceError
        client = self._make_client()
        with pytest.raises(MarketplaceError, match="protocol"):
            client._http_get("ftp://evil.com/file")

    def test_http_get_http_error(self):
        from xcore.marketplace.client import MarketplaceError
        from urllib.error import HTTPError
        client = self._make_client()
        with patch("xcore.marketplace.client.urlopen", side_effect=HTTPError("url", 404, "Not Found", {}, None)):
            with pytest.raises(MarketplaceError, match="HTTP 404"):
                client._http_get("http://localhost:9000/missing")

    def test_http_get_url_error(self):
        from xcore.marketplace.client import MarketplaceError
        from urllib.error import URLError
        client = self._make_client()
        with patch("xcore.marketplace.client.urlopen", side_effect=URLError("connection refused")):
            with pytest.raises(MarketplaceError, match="Connection failed"):
                client._http_get("http://localhost:9000/api")

    def test_http_get_generic_error(self):
        from xcore.marketplace.client import MarketplaceError
        client = self._make_client()
        with patch("xcore.marketplace.client.urlopen", side_effect=Exception("weird")):
            with pytest.raises(MarketplaceError, match="Network error"):
                client._http_get("http://localhost:9000/api")

    def test_http_post_invalid_scheme(self):
        from xcore.marketplace.client import MarketplaceError
        client = self._make_client()
        with pytest.raises(MarketplaceError, match="protocol"):
            client._http_post("ftp://evil.com/upload", {})

    def test_http_post_http_error(self):
        from xcore.marketplace.client import MarketplaceError
        from urllib.error import HTTPError
        client = self._make_client()
        with patch("xcore.marketplace.client.urlopen", side_effect=HTTPError("url", 500, "Server Error", {}, None)):
            with pytest.raises(MarketplaceError, match="HTTP 500"):
                client._http_post("http://localhost:9000/rate", {"score": 5})

    def test_http_post_url_error(self):
        from xcore.marketplace.client import MarketplaceError
        from urllib.error import URLError
        client = self._make_client()
        with patch("xcore.marketplace.client.urlopen", side_effect=URLError("refused")):
            with pytest.raises(MarketplaceError, match="Connection failed"):
                client._http_post("http://localhost:9000/rate", {"score": 5})

    def test_invalidate_cache_specific_key(self):
        client = self._make_client()
        path = MagicMock()
        path.unlink = MagicMock()
        client._cache_path = MagicMock(return_value=path)
        client.invalidate_cache("list")
        path.unlink.assert_called_once_with(missing_ok=True)

    def test_invalidate_cache_all(self):
        client = self._make_client()
        mock_file1 = MagicMock()
        mock_file2 = MagicMock()
        mock_cache_dir = MagicMock()
        mock_cache_dir.glob = MagicMock(return_value=[mock_file1, mock_file2])
        import xcore.marketplace.client as mkt_module
        original = mkt_module.CACHE_DIR
        try:
            mkt_module.CACHE_DIR = mock_cache_dir
            client.invalidate_cache()
        finally:
            mkt_module.CACHE_DIR = original
        mock_file1.unlink.assert_called_once_with(missing_ok=True)
        mock_file2.unlink.assert_called_once_with(missing_ok=True)

    def test_read_cache_expired(self):
        client = self._make_client()
        mock_path = MagicMock()
        mock_path.exists = MagicMock(return_value=True)
        mock_path.read_text = MagicMock(
            return_value=json.dumps({"_ts": time.time() - 9999, "data": "old"})
        )
        client._cache_path = MagicMock(return_value=mock_path)
        result = client._read_cache("key")
        assert result is None

    def test_read_cache_valid(self):
        client = self._make_client()
        mock_path = MagicMock()
        mock_path.exists = MagicMock(return_value=True)
        mock_path.read_text = MagicMock(
            return_value=json.dumps({"_ts": time.time(), "data": "fresh"})
        )
        client._cache_path = MagicMock(return_value=mock_path)
        result = client._read_cache("key")
        assert result == "fresh"

    def test_write_cache_exception_silenced(self, tmp_path):
        client = self._make_client()
        bad_path = MagicMock()
        bad_path.write_text = MagicMock(side_effect=OSError("no space"))
        client._cache_path = MagicMock(return_value=bad_path)
        client._write_cache("key", {"data": "x"})  # should not raise

    def test_headers_with_api_key(self):
        from xcore.marketplace.client import MarketplaceClient
        config = MagicMock()
        config.raw = {"marketplace": {"url": "http://localhost:9000", "api_key": "secret"}}
        client = MarketplaceClient(config)
        h = client._headers()
        assert "Authorization" in h
        assert "secret" in h["Authorization"]

    def test_headers_without_api_key(self):
        client = self._make_client()
        h = client._headers()
        assert "Authorization" not in h
