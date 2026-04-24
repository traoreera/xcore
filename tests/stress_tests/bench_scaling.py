import asyncio
import time
import os
import psutil
from pathlib import Path
import matplotlib.pyplot as plt
from xcore.kernel.sandbox.process_manager import SandboxProcessManager
from xcore.kernel.security.validation import ManifestValidator

async def bench_scaling_plugins():
    # Load manifest using official validator
    validator = ManifestValidator()
    base_plugin_dir = Path("security_exploits/attacker_plugin").resolve()
    manifest = validator.load_and_validate(base_plugin_dir)

    # Define a target list of scaling steps
    num_plugins_target = [1, 5, 10, 20] # Reduced for sandbox stability in constrained env

    latencies = []
    mem_usages = []

    process = psutil.Process(os.getpid())

    print(f"--- Sandbox Scaling Benchmark ---")

    managers = []

    try:
        for n in num_plugins_target:
            # Load up to n plugins
            current_count = len(managers)
            for i in range(current_count, n):
                # Create a NEW manifest instance for each plugin (required by manager)
                p_manifest = validator.load_and_validate(base_plugin_dir)
                p_manifest.name = f"bench_plugin_{i}"

                manager = SandboxProcessManager(p_manifest)
                await manager.start()
                managers.append(manager)

            print(f"Plugins loaded: {len(managers)}")

            # Warm up all plugins
            for m in managers:
                await m.call("ping", {})

            # Measure memory (System-wide + Core process)
            mem = process.memory_info().rss / (1024 * 1024) # MB
            # We also want to see memory of all children
            total_mem = mem
            for m in managers:
                 if m._process:
                     try:
                         total_mem += psutil.Process(m._process.pid).memory_info().rss / (1024 * 1024)
                     except psutil.NoSuchProcess:
                         pass

            mem_usages.append(total_mem)

            # Measure RPC latency (Sequential calls)
            start_time = time.perf_counter()
            for m in managers:
                await m.call("ping", {})
            end_time = time.perf_counter()

            avg_latency = (end_time - start_time) / len(managers) * 1000
            latencies.append(avg_latency)

            print(f"  Avg RPC Latency: {avg_latency:.4f} ms | Total Sandbox Mem: {total_mem:.2f} MB")

    finally:
        print("Cleaning up plugins...")
        for m in managers:
            await m.stop()

    # Plotting
    os.makedirs("tests/stress_tests/data", exist_ok=True)
    plt.figure(figsize=(10, 5))

    plt.subplot(1, 2, 1)
    plt.plot(num_plugins_target[:len(mem_usages)], mem_usages, marker='o')
    plt.title("Total Sandbox Memory Usage")
    plt.xlabel("Number of Plugins")
    plt.ylabel("Total Memory (MB)")
    plt.grid(True)

    plt.subplot(1, 2, 2)
    plt.plot(num_plugins_target[:len(latencies)], latencies, marker='s', color='r')
    plt.title("Avg RPC Latency vs Load")
    plt.xlabel("Number of Plugins")
    plt.ylabel("Latency (ms)")
    plt.grid(True)

    plt.tight_layout()
    plt.savefig("tests/stress_tests/data/sandbox_scaling.png")
    print("\nSaved benchmark plot to tests/stress_tests/data/sandbox_scaling.png")

if __name__ == "__main__":
    asyncio.run(bench_scaling_plugins())
