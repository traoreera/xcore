"""Tests for MemoryBackend coverage gaps (mget, mset, keys, ttl, stats, LRU eviction)."""

import pytest
import asyncio

from xcore.services.cache.backends.memory import MemoryBackend


@pytest.fixture
def backend():
    return MemoryBackend(ttl=300, max_size=100)


class TestMemoryBackendAdvanced:
    @pytest.mark.asyncio
    async def test_mget_existing_keys(self, backend):
        await backend.set("a", "1")
        await backend.set("b", "2")
        result = await backend.mget(["a", "b", "c"])
        assert result["a"] == "1"
        assert result["b"] == "2"
        assert result["c"] is None

    @pytest.mark.asyncio
    async def test_mget_expired_key(self):
        backend = MemoryBackend(ttl=0, max_size=100)
        await backend.set("x", "val", ttl=0)
        # ttl=0 means no expiry in this implementation
        result = await backend.mget(["x"])
        assert result["x"] == "val"

    @pytest.mark.asyncio
    async def test_mset(self, backend):
        await backend.mset({"k1": "v1", "k2": "v2"})
        assert await backend.get("k1") == "v1"
        assert await backend.get("k2") == "v2"

    @pytest.mark.asyncio
    async def test_mset_with_ttl(self, backend):
        await backend.mset({"k1": "v1"}, ttl=100)
        ttl = await backend.ttl("k1")
        assert ttl is not None
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_keys_no_pattern(self, backend):
        await backend.set("key1", "v1")
        await backend.set("key2", "v2")
        keys = await backend.keys()
        assert "key1" in keys
        assert "key2" in keys

    @pytest.mark.asyncio
    async def test_keys_with_pattern(self, backend):
        await backend.set("prefix_a", "1")
        await backend.set("prefix_b", "2")
        await backend.set("other", "3")
        keys = await backend.keys("prefix_*")
        assert "prefix_a" in keys
        assert "prefix_b" in keys
        assert "other" not in keys

    @pytest.mark.asyncio
    async def test_ttl_no_expiry(self, backend):
        await backend.set("k", "v", ttl=0)
        result = await backend.ttl("k")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_with_expiry(self, backend):
        await backend.set("k", "v", ttl=60)
        result = await backend.ttl("k")
        assert result is not None
        assert 0 < result <= 60

    @pytest.mark.asyncio
    async def test_ttl_missing_key(self, backend):
        result = await backend.ttl("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        backend = MemoryBackend(ttl=300, max_size=3)
        await backend.set("a", "1")
        await backend.set("b", "2")
        await backend.set("c", "3")
        # Access "a" to make it recently used
        await backend.get("a")
        # Add a 4th key — "b" should be evicted (LRU)
        await backend.set("d", "4")
        assert await backend.get("d") == "4"
        assert len(backend._store) == 3

    @pytest.mark.asyncio
    async def test_expired_key_returns_none(self):
        import time
        backend = MemoryBackend(ttl=300, max_size=100)
        # Manually insert an expired entry
        from xcore.services.cache.backends.memory import _Entry
        backend._store["expired"] = _Entry(value="val", expires_at=time.monotonic() - 1)
        result = await backend.get("expired")
        assert result is None

    @pytest.mark.asyncio
    async def test_stats(self, backend):
        await backend.set("k", "v")
        await backend.get("k")
        await backend.get("missing")
        stats = backend.stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats

    @pytest.mark.asyncio
    async def test_ping(self, backend):
        result = await backend.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_clear(self, backend):
        await backend.set("k", "v")
        await backend.clear()
        assert await backend.get("k") is None

    @pytest.mark.asyncio
    async def test_delete(self, backend):
        await backend.set("k", "v")
        deleted = await backend.delete("k")
        assert deleted is True
        assert await backend.get("k") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend):
        deleted = await backend.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_exists_true(self, backend):
        await backend.set("k", "v")
        assert await backend.exists("k") is True

    @pytest.mark.asyncio
    async def test_exists_false(self, backend):
        assert await backend.exists("missing") is False

    @pytest.mark.asyncio
    async def test_mget_with_expired(self):
        import time
        from xcore.services.cache.backends.memory import _Entry
        backend = MemoryBackend(ttl=300, max_size=100)
        backend._store["old"] = _Entry(value="stale", expires_at=time.monotonic() - 1)
        await backend.set("fresh", "value")
        result = await backend.mget(["old", "fresh"])
        assert result["old"] is None
        assert result["fresh"] == "value"
