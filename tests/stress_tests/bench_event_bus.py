import asyncio
import time
import matplotlib.pyplot as plt
import numpy as np
from xcore.kernel.events.bus import EventBus
import os

async def bench_event_bus():
    bus = EventBus()
    num_subscribers = [1, 10, 100, 500, 1000]
    num_emits = 1000

    throughputs = []
    latencies = []

    print(f"--- Event Bus Benchmark ({num_emits} emits per run) ---")

    for n in num_subscribers:
        # Clear bus
        bus.clear()

        # Add subscribers
        for i in range(n):
            async def handler(event):
                pass
            bus.subscribe("test.event", handler)

        # Warmup
        await bus.emit("test.event", {"data": "warmup"})

        start_time = time.perf_counter()
        for _ in range(num_emits):
            await bus.emit("test.event", {"data": "test"})
        end_time = time.perf_counter()

        duration = end_time - start_time
        throughput = (num_emits * n) / duration # total handler calls per sec
        latency = (duration / num_emits) * 1000 # ms per emit

        throughputs.append(throughput)
        latencies.append(latency)
        print(f"Subscribers: {n:4} | Duration: {duration:.4f}s | Throughput: {throughput:10.2f} calls/s | Latency: {latency:.4f} ms")

    # Benchmark with Wildcards
    print("\n--- Wildcard Benchmark (100 subscribers, varying wildcard patterns) ---")
    bus.clear()
    for i in range(100):
        async def handler(event): pass
        bus.subscribe("test.*", handler)

    num_wildcards = [0, 10, 50, 100, 200]
    wildcard_latencies = []

    for nw in num_wildcards:
        # Add dummy wildcard patterns that don't match
        for i in range(nw):
            async def dummy(event): pass
            bus.subscribe(f"other.{i}.*", dummy)

        start_time = time.perf_counter()
        for _ in range(num_emits):
            await bus.emit("test.event", {"data": "test"})
        end_time = time.perf_counter()

        latency = (end_time - start_time) / num_emits * 1000
        wildcard_latencies.append(latency)
        print(f"Dummy Wildcards: {nw:3} | Latency: {latency:.4f} ms")

    # Plotting
    os.makedirs("tests/stress_tests/data", exist_ok=True)

    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.plot(num_subscribers, throughputs, marker='o')
    plt.title("Event Bus Throughput")
    plt.xlabel("Number of Subscribers")
    plt.ylabel("Calls per second")
    plt.grid(True)

    plt.subplot(1, 2, 2)
    plt.plot(num_subscribers, latencies, marker='s', color='r')
    plt.title("Event Bus Latency")
    plt.xlabel("Number of Subscribers")
    plt.ylabel("Latency (ms) per emit")
    plt.grid(True)

    plt.tight_layout()
    plt.savefig("tests/stress_tests/data/event_bus_bench.png")
    print("\nSaved benchmark plot to tests/stress_tests/data/event_bus_bench.png")

if __name__ == "__main__":
    asyncio.run(bench_event_bus())
