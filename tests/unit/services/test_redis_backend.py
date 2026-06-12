
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from xcore.services.cache.backends.redis import RedisCacheBackend

class TestRedisCacheBackend:
    @pytest.fixture
    def cfg(self):
        from types import SimpleNamespace
        return SimpleNamespace(url="redis://localhost:6379", ttl=60)

    @pytest.fixture
    def backend(self, cfg):
        return RedisCacheBackend(url=cfg.url, ttl=cfg.ttl)

    @pytest.mark.asyncio
    async def test_connect(self, backend):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_from_url.return_value = mock_client

            await backend.connect()

            mock_from_url.assert_called_once_with("redis://localhost:6379", decode_responses=True)
            mock_client.ping.assert_called_once()
            assert backend._client == mock_client

    @pytest.mark.asyncio
    async def test_connect_import_error(self, backend):
        with patch.dict("sys.modules", {"redis.asyncio": None}):
            with pytest.raises(ImportError) as exc:
                await backend.connect()
            assert "redis non installé" in str(exc.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client

        await backend.disconnect()

        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_json(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client
        mock_client.get.return_value = json.dumps({"a": 1})

        val = await backend.get("key")
        assert val == {"a": 1}

    @pytest.mark.asyncio
    async def test_get_raw(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client
        mock_client.get.return_value = "plain string"

        val = await backend.get("key")
        assert val == "plain string"

    @pytest.mark.asyncio
    async def test_get_none(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client
        mock_client.get.return_value = None

        val = await backend.get("key")
        assert val is None

    @pytest.mark.asyncio
    async def test_set_json(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client

        await backend.set("key", {"a": 1})
        mock_client.set.assert_called_once_with("key", '{"a": 1}', ex=60)

    @pytest.mark.asyncio
    async def test_set_raw(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client

        await backend.set("key", "value", ttl=10)
        mock_client.set.assert_called_once_with("key", "value", ex=10)

    @pytest.mark.asyncio
    async def test_mget(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client
        mock_client.mget.return_value = ['{"a": 1}', None, "raw"]

        res = await backend.mget(["k1", "k2", "k3"])
        assert res == {"k1": {"a": 1}, "k2": None, "k3": "raw"}

    @pytest.mark.asyncio
    async def test_mget_empty(self, backend):
        res = await backend.mget([])
        assert res == {}

    @pytest.mark.asyncio
    async def test_mset(self, backend):
        mock_client = MagicMock()
        backend._client = mock_client
        mock_pipe = AsyncMock()
        # set is not awaited in redis pipeline
        mock_pipe.set = MagicMock()
        mock_client.pipeline.return_value.__aenter__.return_value = mock_pipe

        await backend.mset({"k1": 1, "k2": "v2"}, ttl=20)

        assert mock_pipe.set.call_count == 2
        mock_pipe.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_exists_clear(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client

        mock_client.delete.return_value = 1
        assert await backend.delete("k") is True

        mock_client.exists.return_value = 0
        assert await backend.exists("k") is False

        await backend.clear()
        mock_client.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_keys_ttl_ping(self, backend):
        mock_client = AsyncMock()
        backend._client = mock_client

        mock_client.keys.return_value = ["a", "b"]
        assert await backend.keys() == ["a", "b"]

        mock_client.ttl.return_value = 45
        assert await backend.ttl("k") == 45.0

        mock_client.ttl.return_value = -2
        assert await backend.ttl("k") is None

        mock_client.ping.return_value = True
        assert await backend.ping() is True

    def test_stats(self, backend):
        s = backend.stats()
        assert s["backend"] == "redis"
        assert "redis://" in s["url"]
