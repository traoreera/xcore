## 2025-03-04 - [Optimization of EventBus dispatch overhead]
**Learning:** `inspect.iscoroutinefunction` is surprisingly expensive when called in hot paths like event emission or permission checks (~30x slower than a boolean check). Furthermore, creating per-emission wrapper coroutines for synchronous handlers significantly increases dispatch latency and GC pressure.
**Action:** Always pre-calculate and cache the `is_async` status of callable handlers during the registration/subscription phase. In emission loops, use this cached flag to branch between direct calls and `await` calls to minimize overhead.

## 2025-05-14 - [Memoization in Permission Evaluation]
**Learning:** Permission evaluation involving glob patterns (via `fnmatch`) is computationally expensive, especially when performed on every plugin call. In XCore, this was consuming ~53µs per call set (multiple resources/actions).
**Action:** Implement a memoization layer (simple dictionary cache) for permission check results. This reduced evaluation time by ~70%, bringing it down to ~16µs. Always invalidate the cache when underlying policies are modified.

## 2026-03-19 - [Batching Cache Operations]
**Learning:** Sequential network round-trips for multiple cache operations (individual GET/SET) are extremely expensive in distributed environments (e.g., Redis). Using native batching (MGET) or pipelining (MSET with individual TTLs) reduces the total latency from $O(N \times \text{latency})$ to $O(\text{latency})$.
**Action:** Implement and use dedicated `mget` and `mset` methods in cache backends. Use `MGET` for batch reads and `pipeline` for batch writes with individual TTLs in the Redis backend.
