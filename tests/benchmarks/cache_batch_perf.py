import asyncio
import time
import unittest.mock as mock

from xcore.services.cache.backends.memory import MemoryBackend
from xcore.services.cache.backends.redis import RedisCacheBackend


async def benchmark_memory():
    print("\n--- MemoryBackend Benchmark ---")
    backend = MemoryBackend()
    keys = [f"key:{i}" for i in range(100)]
    values = {k: f"val:{i}" for i, k in enumerate(keys)}

    # Baseline: individual sets
    start = time.perf_counter()
    for k, v in values.items():
        await backend.set(k, v)
    end = time.perf_counter()
    print(f"Sequential SET (100 keys): {(end-start)*1000:.2f}ms")

    # Optimization: mset
    start = time.perf_counter()
    await backend.mset(values)
    end = time.perf_counter()
    print(f"Native MSET (100 keys): {(end-start)*1000:.2f}ms")

    # Baseline: individual gets
    start = time.perf_counter()
    for k in keys:
        await backend.get(k)
    end = time.perf_counter()
    print(f"Sequential GET (100 keys): {(end-start)*1000:.2f}ms")

    # Optimization: mget
    start = time.perf_counter()
    await backend.mget(keys)
    end = time.perf_counter()
    print(f"Native MGET (100 keys): {(end-start)*1000:.2f}ms")


async def benchmark_redis_mocked():
    print("\n--- RedisCacheBackend (Mocked Latency) Benchmark ---")

    # Simulation of 2ms network latency per call
    LATENCY = 0.002

    class MockRedis:
        def __init__(self):
            self.data = {}

        async def ping(self):
            return True

        async def get(self, key):
            await asyncio.sleep(LATENCY)
            return self.data.get(key)

        async def set(self, key, val, ex=None):
            await asyncio.sleep(LATENCY)
            self.data[key] = val

        async def mget(self, keys):
            await asyncio.sleep(LATENCY)
            return [self.data.get(k) for k in keys]

        def pipeline(self):
            return MockPipeline(self)

        async def aclose(self):
            pass

    class MockPipeline:
        def __init__(self, redis):
            self.redis = redis
            self.cmds = []

        def set(self, key, val, ex=None):
            self.cmds.append(("set", key, val, ex))
            return self

        async def execute(self):
            await asyncio.sleep(LATENCY)  # Batch latency
            for cmd, *args in self.cmds:
                if cmd == "set":
                    self.redis.data[args[0]] = args[1]
            return [True] * len(self.cmds)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with mock.patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = MockRedis()
        mock_from_url.return_value = mock_redis

        backend = RedisCacheBackend(url="redis://localhost")
        await backend.connect()

        keys = [f"key:{i}" for i in range(100)]
        values = {k: f"val:{i}" for i, k in enumerate(keys)}

        # 1. SET Benchmark
        # Sequential
        start = time.perf_counter()
        for k, v in values.items():
            await backend.set(k, v)
        end = time.perf_counter()
        print(
            f"Sequential SET (100 keys, {LATENCY*1000}ms latency): {(end-start)*1000:.2f}ms"
        )

        # MSET (Optimized)
        start = time.perf_counter()
        await backend.mset(values)
        end = time.perf_counter()
        print(
            f"Optimized MSET (Pipeline) (100 keys, {LATENCY*1000}ms latency): {(end-start)*1000:.2f}ms"
        )

        # 2. GET Benchmark
        # Sequential
        start = time.perf_counter()
        for k in keys:
            await backend.get(k)
        end = time.perf_counter()
        print(
            f"Sequential GET (100 keys, {LATENCY*1000}ms latency): {(end-start)*1000:.2f}ms"
        )

        # MGET (Optimized)
        start = time.perf_counter()
        await backend.mget(keys)
        end = time.perf_counter()
        print(
            f"Optimized MGET (Native) (100 keys, {LATENCY*1000}ms latency): {(end-start)*1000:.2f}ms"
        )


if __name__ == "__main__":
    asyncio.run(benchmark_memory())
    asyncio.run(benchmark_redis_mocked())
