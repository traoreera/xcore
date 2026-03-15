import time
import random
import string
import logging
from xcore.kernel.permissions.engine import PermissionEngine
from xcore.kernel.permissions.policies import PolicyEffect

# Disable logging for benchmark
logging.getLogger("xcore.permissions.engine").setLevel(logging.ERROR)

def benchmark_permissions():
    engine = PermissionEngine()

    # Setup some policies
    plugins = ["plugin_" + str(i) for i in range(10)]
    for p in plugins:
        raw_perms = [
            {"resource": "db.*", "actions": ["read", "write"], "effect": "allow"},
            {"resource": "cache.*", "actions": ["read"], "effect": "allow"},
            {"resource": "os.*", "actions": ["*"], "effect": "deny"},
            {"resource": "api.v1.*", "actions": ["execute"], "effect": "allow"},
            {"resource": "admin.*", "actions": ["*"], "effect": "deny"},
        ]
        engine.load_from_manifest(p, raw_perms)

    resources = ["db.users", "cache.items", "os.delete", "api.v1.login", "admin.config", "other.resource"]
    actions = ["read", "write", "execute", "delete"]

    # Pre-generate random samples to avoid overhead of random.choice in the loop
    iterations = 200000
    samples = [(random.choice(plugins), random.choice(resources), random.choice(actions)) for _ in range(iterations)]

    # Warm up to fill the cache
    for p, r, a in samples[:1000]:
        engine.allows(p, r, a)

    start_time = time.perf_counter()

    for p, r, a in samples:
        engine.allows(p, r, a)

    end_time = time.perf_counter()
    total_time = end_time - start_time
    print(f"Total time for {iterations} iterations: {total_time:.4f} seconds")
    print(f"Average time per iteration: {total_time/iterations*1e6:.4f} microseconds")

if __name__ == "__main__":
    benchmark_permissions()
