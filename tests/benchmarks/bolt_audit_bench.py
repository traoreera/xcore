
import collections
import timeit

# Simulation of PermissionEngine audit log
audit_log = collections.deque(maxlen=100000)
for i in range(100000):
    audit_log.append({"plugin": f"plugin_{i%10}", "action": "test"})

def original():
    plugin_name = "plugin_5"
    limit = 100
    log = [e for e in audit_log if e["plugin"] == plugin_name]
    return log[-limit:]

def optimized():
    plugin_name = "plugin_5"
    limit = 100
    results = []
    for entry in reversed(audit_log):
        if entry["plugin"] == plugin_name:
            results.append(entry)
            if len(results) >= limit:
                break
    return list(reversed(results))

def run_bench():
    n = 100
    t1 = timeit.timeit(original, number=n)
    t2 = timeit.timeit(optimized, number=n)
    print(f"Audit log filtering (100k entries, limit 100):")
    print(f"  Original:  {t1:.4f}s")
    print(f"  Optimized: {t2:.4f}s")
    print(f"  Speedup:   {t1/t2:.2f}x")

if __name__ == "__main__":
    run_bench()
