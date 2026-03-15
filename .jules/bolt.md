## 2025-03-04 - [Optimization of EventBus dispatch overhead]
**Learning:** `inspect.iscoroutinefunction` is surprisingly expensive when called in hot paths like event emission or permission checks (~30x slower than a boolean check). Furthermore, creating per-emission wrapper coroutines for synchronous handlers significantly increases dispatch latency and GC pressure.
**Action:** Always pre-calculate and cache the `is_async` status of callable handlers during the registration/subscription phase. In emission loops, use this cached flag to branch between direct calls and `await` calls to minimize overhead.

## 2026-03-15 - [Permission Evaluation Memoization]
**Learning:** Permission checks are high-frequency "hot paths" in a plugin system. Repeated policy evaluations involving glob matching (e.g., via `fnmatch`) introduce significant cumulative latency. Using a simple dictionary-based memoization cache can provide a substantial performance boost (~60% speedup in benchmarks) with minimal code complexity.
**Action:** Implement memoization for permission checks where policies are relatively static. Ensure robust cache invalidation whenever the underlying policy set is modified (e.g., during plugin (re)loads).
