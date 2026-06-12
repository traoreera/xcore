
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from xcore.services.database.adapters.redis import RedisAdapter

class TestRedisAdapter:
    @pytest.fixture
    def cfg(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            url="redis://localhost:6379",
            max_connections=20
        )

    @pytest.fixture
    def adapter(self, cfg):
        return RedisAdapter("redis_db", cfg)

    @pytest.mark.asyncio
    async def test_connect(self, adapter):
        with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool_from_url:
            with patch("redis.asyncio.Redis") as mock_redis_class:
                mock_client = AsyncMock()
                mock_redis_class.return_value = mock_client

                await adapter.connect()

                mock_pool_from_url.assert_called_once_with(
                    "redis://localhost:6379",
                    max_connections=20,
                    decode_responses=True
                )
                mock_redis_class.assert_called_once()
                mock_client.ping.assert_called_once()
                assert adapter._client == mock_client

    @pytest.mark.asyncio
    async def test_connect_import_error(self, adapter):
        with patch.dict("sys.modules", {"redis.asyncio": None}):
            with pytest.raises(ImportError) as exc:
                await adapter.connect()
            assert "redis non installé" in str(exc.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        mock_client = AsyncMock()
        adapter._client = mock_client

        await adapter.disconnect()

        mock_client.aclose.assert_called_once()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_basic_ops(self, adapter):
        mock_client = AsyncMock()
        adapter._client = mock_client

        # get
        mock_client.get.return_value = "val"
        assert await adapter.get("k") == "val"

        # set
        mock_client.set.return_value = True
        assert await adapter.set("k", "v", ex=10) is True
        mock_client.set.assert_called_with("k", "v", ex=10)

        # delete
        mock_client.delete.return_value = 1
        assert await adapter.delete("k1", "k2") == 1

        # exists
        mock_client.exists.return_value = 1
        assert await adapter.exists("k") is True

    @pytest.mark.asyncio
    async def test_hash_ops(self, adapter):
        mock_client = AsyncMock()
        adapter._client = mock_client

        # hget
        mock_client.hget.return_value = "hv"
        assert await adapter.hget("h", "k") == "hv"

        # hset
        mock_client.hset.return_value = 1
        assert await adapter.hset("h", {"k": "v"}) == 1

        # hgetall
        mock_client.hgetall.return_value = {"k": "v"}
        assert await adapter.hgetall("h") == {"k": "v"}

    def test_client_property(self, adapter):
        mock_client = MagicMock()
        adapter._client = mock_client
        assert adapter.client == mock_client

    @pytest.mark.asyncio
    async def test_ping(self, adapter):
        mock_client = AsyncMock()
        adapter._client = mock_client

        # Success
        mock_client.ping.return_value = True
        ok, msg = await adapter.ping()
        assert ok is True
        assert msg == "ok"

        # Failure
        mock_client.ping.side_effect = Exception("err")
        ok, msg = await adapter.ping()
        assert ok is False
        assert msg == "err"
