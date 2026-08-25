"""Tests for TieredCacheBackend (memory L1 + fake L2 — pure unit, no network I/O)."""

import pytest

from xcore.services.cache.backends.memory import MemoryBackend
from xcore.services.cache.backends.tiered import TieredCacheBackend


class _FakeL2:
    """Stand-in for RedisCacheBackend — same async interface, in-memory dict,
    no network I/O. RedisCacheBackend itself is a thin wrapper around the
    `redis` client and belongs to integration tests with a live Redis."""

    def __init__(self):
        self.store: dict = {}
        self.connected = False
        self.get_calls = 0

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def get(self, key):
        self.get_calls += 1
        return self.store.get(key)

    async def set(self, key, value, ttl=None):
        self.store[key] = value

    async def delete(self, key):
        return self.store.pop(key, None) is not None

    async def exists(self, key):
        return key in self.store

    async def clear(self):
        self.store.clear()

    async def mget(self, keys):
        return {k: self.store.get(k) for k in keys}

    async def mset(self, mapping, ttl=None):
        self.store.update(mapping)

    async def keys(self, pattern=None):
        return list(self.store.keys())

    async def ttl(self, key):
        return None

    async def ping(self):
        return True

    def stats(self):
        return {"backend": "fake-redis", "size": len(self.store)}


@pytest.fixture
def backend():
    return TieredCacheBackend(l1=MemoryBackend(ttl=300, max_size=100), l2=_FakeL2())


class TestTieredCacheBackend:
    @pytest.mark.asyncio
    async def test_connect_delegates_to_l2(self, backend):
        await backend.connect()
        assert backend._l2.connected is True

    @pytest.mark.asyncio
    async def test_set_writes_through_both_layers(self, backend):
        await backend.set("k", "v")
        assert await backend._l1.get("k") == "v"
        assert backend._l2.store["k"] == "v"

    @pytest.mark.asyncio
    async def test_get_hits_l1_without_touching_l2(self, backend):
        await backend.set("k", "v")
        backend._l2.get_calls = 0

        value = await backend.get("k")

        assert value == "v"
        assert backend._l2.get_calls == 0

    @pytest.mark.asyncio
    async def test_get_falls_back_to_l2_and_backfills_l1(self, backend):
        # Valeur écrite directement en L2 — simule un autre nœud.
        backend._l2.store["k"] = "from-l2"

        value = await backend.get("k")

        assert value == "from-l2"
        assert await backend._l1.get("k") == "from-l2"  # repeuplé

    @pytest.mark.asyncio
    async def test_get_miss_on_both_layers(self, backend):
        assert await backend.get("nope") is None

    @pytest.mark.asyncio
    async def test_delete_removes_from_both_layers(self, backend):
        await backend.set("k", "v")
        deleted = await backend.delete("k")
        assert deleted is True
        assert await backend._l1.get("k") is None
        assert "k" not in backend._l2.store

    @pytest.mark.asyncio
    async def test_delete_missing_key_returns_false(self, backend):
        assert await backend.delete("nope") is False

    @pytest.mark.asyncio
    async def test_exists_checks_l1_then_l2(self, backend):
        backend._l2.store["k"] = "v"  # uniquement en L2
        assert await backend.exists("k") is True
        assert await backend.exists("nope") is False

    @pytest.mark.asyncio
    async def test_clear_clears_both_layers(self, backend):
        await backend.set("k", "v")
        await backend.clear()
        assert await backend._l1.get("k") is None
        assert backend._l2.store == {}

    @pytest.mark.asyncio
    async def test_mget_merges_l1_and_l2_and_backfills(self, backend):
        await backend.set("a", 1)  # en L1 et L2
        backend._l2.store["b"] = 2  # uniquement en L2

        results = await backend.mget(["a", "b", "c"])

        assert results == {"a": 1, "b": 2, "c": None}
        assert await backend._l1.get("b") == 2  # repeuplé depuis L2

    @pytest.mark.asyncio
    async def test_mset_writes_through_both_layers(self, backend):
        await backend.mset({"a": 1, "b": 2})
        assert await backend._l1.get("a") == 1
        assert backend._l2.store == {"a": 1, "b": 2}

    @pytest.mark.asyncio
    async def test_keys_reads_from_l2(self, backend):
        backend._l2.store = {"a": 1, "b": 2}
        assert sorted(await backend.keys()) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_ping_delegates_to_l2(self, backend):
        assert await backend.ping() is True

    @pytest.mark.asyncio
    async def test_stats_merges_both_layers(self, backend):
        stats = backend.stats()
        assert stats["backend"] == "tiered"
        assert stats["l1"]["backend"] == "memory"
        assert stats["l2"]["backend"] == "fake-redis"
