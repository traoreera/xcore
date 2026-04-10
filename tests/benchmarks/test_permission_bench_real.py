import logging
import timeit

from xcore.kernel.permissions.engine import PermissionEngine

# Suppress logging during benchmark
logging.getLogger("xcore.permissions.engine").setLevel(logging.ERROR)


def benchmark_permissions():
    engine = PermissionEngine()
    permissions = [
        {"resource": "db.users.*", "actions": ["read"], "effect": "allow"},
        {"resource": "db.admin.*", "actions": ["*"], "effect": "deny"},
        {"resource": "cache.*", "actions": ["read", "write"], "effect": "allow"},
        {"resource": "fs.tmp.*", "actions": ["write"], "effect": "allow"},
        {"resource": "api.v1.*", "actions": ["call"], "effect": "allow"},
        {"resource": "internal.*", "actions": ["*"], "effect": "deny"},
        {"resource": "*", "actions": ["read"], "effect": "allow"},
    ]
    engine.load_from_manifest("test_plugin", permissions)

    resources_actions = [
        ("db.users.profile", "read"),
        ("db.admin.secrets", "read"),
        ("cache.data", "write"),
        ("fs.tmp.file1", "write"),
        ("api.v1.login", "call"),
        ("internal.secrets", "read"),
        ("public.data", "read"),
        ("unknown.resource", "write"),
    ]

    def test_call():
        for res, act in resources_actions:
            engine.allows("test_plugin", res, act)

    iterations = 10000
    timer = timeit.Timer(test_call)
    time_taken = timer.timeit(number=iterations)
    print(f"Time for {iterations} iterations: {time_taken:.4f}s")
    print(f"Average time per call set: {time_taken/iterations*1000000:.2f}µs")


if __name__ == "__main__":
    benchmark_permissions()
