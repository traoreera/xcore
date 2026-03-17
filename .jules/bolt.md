## 2025-03-04 - [Optimization of EventBus dispatch overhead]
**Learning:** `inspect.iscoroutinefunction` is surprisingly expensive when called in hot paths like event emission or permission checks (~30x slower than a boolean check). Furthermore, creating per-emission wrapper coroutines for synchronous handlers significantly increases dispatch latency and GC pressure.
**Action:** Always pre-calculate and cache the `is_async` status of callable handlers during the registration/subscription phase. In emission loops, use this cached flag to branch between direct calls and `await` calls to minimize overhead.

## 2025-03-04 - [Memoization of Permission Checks]
**Learning:** Permission checks involving glob patterns (`fnmatch`) and iterative policy evaluations can become a bottleneck when called on every plugin action. Since policies are relatively static, caching the result of `(plugin, resource, action)` evaluations provides a significant performance boost.
**Action:** Implement a simple dictionary-based cache for permission evaluation results and ensure it is cleared whenever policies are reloaded or modified.
