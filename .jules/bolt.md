## 2025-03-04 - [Optimization of EventBus dispatch overhead]
**Learning:** `inspect.iscoroutinefunction` is surprisingly expensive when called in hot paths like event emission or permission checks (~30x slower than a boolean check). Furthermore, creating per-emission wrapper coroutines for synchronous handlers significantly increases dispatch latency and GC pressure.
**Action:** Always pre-calculate and cache the `is_async` status of callable handlers during the registration/subscription phase. In emission loops, use this cached flag to branch between direct calls and `await` calls to minimize overhead.

## 2025-05-22 - [Memoization of permission evaluations in PermissionEngine]
**Learning:** Permission evaluation involving glob matching (e.g., via `fnmatch.fnmatch`) in a linear loop over policies can become a significant bottleneck (~24µs per call) when invoked on every plugin interaction. Memoizing the results of `(plugin, resource, action)` checks reduces this $O(N)$ operation to an $O(1)$ dictionary lookup, providing a ~5x speedup.
**Action:** Implement a dictionary-based cache for permission checks and ensure explicit cache invalidation whenever the underlying policy sets are modified (e.g., during plugin loading or manual permission grants).
