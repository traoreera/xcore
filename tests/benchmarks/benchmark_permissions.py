
import time
import random
from xcore.kernel.permissions.engine import PermissionEngine

def benchmark_permission_engine():
    engine = PermissionEngine()

    # Setup policies for a few plugins
    plugins = ["plugin_a", "plugin_b", "plugin_c"]
    for p in plugins:
        policies = [
            {"resource": "action.read", "actions": ["execute"], "effect": "allow"},
            {"resource": "action.write", "actions": ["execute"], "effect": "allow"},
            {"resource": "db.*", "actions": ["read", "write"], "effect": "allow"},
            {"resource": "admin.*", "actions": ["*"], "effect": "deny"},
        ]
        engine.load_from_manifest(p, policies)

    # Warm up
    for _ in range(100):
        engine.allows("plugin_a", "action.read", "execute")

    iterations = 100000
    start_time = time.perf_counter()
    for i in range(iterations):
        p = plugins[i % len(plugins)]
        engine.allows(p, "action.read", "execute")
    end_time = time.perf_counter()

    duration = end_time - start_time
    print(f"Time taken for {iterations} calls: {duration:.4f}s")
    print(f"Average time per call: {duration/iterations*1e6:.4f}us")

if __name__ == "__main__":
    benchmark_permission_engine()
