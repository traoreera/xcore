import asyncio
import time
import os
import psutil
from pathlib import Path
import matplotlib.pyplot as plt
from xcore.kernel.sandbox.process_manager import SandboxProcessManager
from xcore.kernel.security.validation import ManifestValidator

async def bench_lifecycle():
    validator = ManifestValidator()
    base_plugin_dir = Path("security_exploits/attacker_plugin").resolve()
    manifest = validator.load_and_validate(base_plugin_dir)

    num_cycles = 50
    print(f"--- Sandbox Lifecycle Benchmark ({num_cycles} load/unload cycles) ---")

    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / (1024 * 1024)

    start_time = time.perf_counter()

    for i in range(num_cycles):
        p_manifest = validator.load_and_validate(base_plugin_dir)
        p_manifest.name = f"lifecycle_plugin_{i}"
        manager = SandboxProcessManager(p_manifest)

        await manager.start()
        await manager.call("ping", {})
        await manager.stop()

        if (i+1) % 10 == 0:
            print(f"  Cycle {i+1}/{num_cycles} complete")

    end_time = time.perf_counter()
    duration = end_time - start_time
    mem_after = process.memory_info().rss / (1024 * 1024)

    print(f"Total Duration: {duration:.2f}s")
    print(f"Avg Cycle Time: {duration/num_cycles*1000:.2f}ms")
    print(f"Mem Leak check: Before {mem_before:.2f}MB | After {mem_after:.2f}MB | Diff {mem_after - mem_before:.2f}MB")

if __name__ == "__main__":
    asyncio.run(bench_lifecycle())
