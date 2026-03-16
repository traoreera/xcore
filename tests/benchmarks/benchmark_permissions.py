import time
import logging
from xcore.kernel.permissions.engine import PermissionEngine

# Disable logging for benchmark
logging.getLogger("xcore.permissions.engine").setLevel(logging.ERROR)

def benchmark_permissions():
    engine = PermissionEngine()
    plugin_name = "test_plugin"

    # Setup some policies
    # Adding more policies to make the linear search more significant
    policies = [
        {"resource": f"db.table_{i}.*", "actions": ["read", "write"], "effect": "allow"}
        for i in range(20)
    ]
    policies.append({"resource": "api.v1.*", "actions": ["*"], "effect": "allow"})
    policies.append({"resource": "os.*", "actions": ["*"], "effect": "deny"})

    engine.load_from_manifest(plugin_name, policies)

    # Resources and actions for testing
    test_cases = [
        ("db.table_19.row_1", "read"),
        ("api.v1.login", "post"),
        ("os.system", "write"), # Denied
        ("unknown.resource", "read"), # Denied (fail-closed)
    ]

    # Warm up
    for _ in range(1000):
        for res, act in test_cases:
            engine.allows(plugin_name, res, act)

    iterations = 50000
    start_time = time.perf_counter()
    for _ in range(iterations):
        for res, act in test_cases:
            engine.allows(plugin_name, res, act)
    end_time = time.perf_counter()

    total_calls = iterations * len(test_cases)
    duration = end_time - start_time
    print(f"Total calls: {total_calls}")
    print(f"Total time: {duration:.4f}s")
    print(f"Average time per call: {(duration/total_calls)*1000000:.4f}µs")

if __name__ == "__main__":
    benchmark_permissions()
