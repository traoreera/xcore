"""
Tests for CacheService.
"""


import pytest

from xcore.services.base import ServiceStatus
from xcore.services.cache.service import CacheService


class TestCacheService:
    """Test CacheService functionality."""

    @pytest.fixture
    def memory_config(self):
        """Memory backend configuration."""
        from types import SimpleNamespace

        return SimpleNamespace(backend="memory", url=None, ttl=300, max_size=1000)

    @pytest.fixture
    def redis_config(self):
        """Redis backend configuration."""
        from types import SimpleNamespace

        return SimpleNamespace(
            backend="redis", url="redis://localhost:6379/0", ttl=300, max_size=1000
        )

    @pytest.mark.asyncio
    async def test_init_memory_backend(self, memory_config):
        """Test initializing memory backend."""
        cache = CacheService(memory_config)
        await cache.init()

        assert cache._status == ServiceStatus.READY
        assert cache._backend is not None

    @pytest.mark.asyncio
    async def test_init_redis_backend_requires_url(self, redis_config):
        """Test Redis backend requires URL."""
        redis_config.url = None
        cache = CacheService(redis_config)

        with pytest.raises(ValueError) as exc:
            await cache.init()

        assert "url obligatoire" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_set_delete(self, memory_config):
        """Test basic cache operations."""
        cache = CacheService(memory_config)
        await cache.init()

        # Set value
        await cache.set("key1", "value1")

        # Get value
        value = await cache.get("key1")
        assert value == "value1"

        # Delete value
        deleted = await cache.delete("key1")
        assert deleted is True

        # Verify deletion
        value = await cache.get("key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_exists(self, memory_config):
        """Test exists operation."""
        cache = CacheService(memory_config)
        await cache.init()

        await cache.set("key1", "value1")

        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_clear(self, memory_config):
        """Test clear operation."""
        cache = CacheService(memory_config)
        await cache.init()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_get_or_set(self, memory_config):
        """Test get_or_set pattern."""
        cache = CacheService(memory_config)
        await cache.init()

        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return {"data": "expensive"}

        # First call - factory executed
        result = await cache.get_or_set("key1", factory, ttl=60)
        assert result["data"] == "expensive"
        assert call_count == 1

        # Second call - cached value
        result = await cache.get_or_set("key1", factory, ttl=60)
        assert result["data"] == "expensive"
        assert call_count == 1  # Factory not called again

    @pytest.mark.asyncio
    async def test_mget_mset(self, memory_config):
        """Test multi-get and multi-set."""
        cache = CacheService(memory_config)
        await cache.init()

        # Multi-set
        await cache.mset({"a": 1, "b": 2, "c": 3})

        # Multi-get
        results = await cache.mget(["a", "b", "c", "d"])
        assert results["a"] == 1
        assert results["b"] == 2
        assert results["c"] == 3
        assert results["d"] is None

    @pytest.mark.asyncio
    async def test_ttl_override(self, memory_config):
        """Test TTL override."""
        cache = CacheService(memory_config)
        await cache.init()

        # Set with custom TTL
        await cache.set("key1", "value1", ttl=10)

    @pytest.mark.asyncio
    async def test_shutdown(self, memory_config):
        """Test shutdown."""
        cache = CacheService(memory_config)
        await cache.init()

        await cache.shutdown()

        assert cache._status == ServiceStatus.STOPPED

    @pytest.mark.asyncio
    async def test_health_check(self, memory_config):
        """Test health check."""
        cache = CacheService(memory_config)
        await cache.init()

        ok, msg = await cache.health_check()

        assert ok is True
        assert msg == "ok"

    def test_status(self, memory_config):
        """Test status method."""
        cache = CacheService(memory_config)

        status = cache.status()

        assert status["name"] == "cache"
        assert "status" in status
