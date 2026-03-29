## 2025-03-04 - [Optimization of EventBus dispatch overhead]
**Learning:** `inspect.iscoroutinefunction` is surprisingly expensive when called in hot paths like event emission or permission checks (~30x slower than a boolean check). Furthermore, creating per-emission wrapper coroutines for synchronous handlers significantly increases dispatch latency and GC pressure.
**Action:** Always pre-calculate and cache the `is_async` status of callable handlers during the registration/subscription phase. In emission loops, use this cached flag to branch between direct calls and `await` calls to minimize overhead.

## 2025-05-14 - [Memoization in Permission Evaluation]
**Learning:** Permission evaluation involving glob patterns (via `fnmatch`) is computationally expensive, especially when performed on every plugin call. In XCore, this was consuming ~53µs per call set (multiple resources/actions).
**Action:** Implement a memoization layer (simple dictionary cache) for permission check results. This reduced evaluation time by ~70%, bringing it down to ~16µs. Always invalidate the cache when underlying policies are modified.

## 2026-03-19 - [Batching Cache Operations]
**Learning:** Sequential network round-trips for multiple cache operations (individual GET/SET) are extremely expensive in distributed environments (e.g., Redis). Using native batching (MGET) or pipelining (MSET with individual TTLs) reduces the total latency from $O(N \times \text{latency})$ to $O(\text{latency})$.
**Action:** Implement and use dedicated `mget` and `mset` methods in cache backends. Use `MGET` for batch reads and `pipeline` for batch writes with individual TTLs in the Redis backend.

## 2026-03-25 - [Short-circuiting Permission Matching]
**Learning:** In the `Policy.matches` method, evaluating resource glob patterns (via `fnmatch.fnmatch`) before checking for action matches is inefficient because string pattern matching is significantly slower than list lookups. Since many checks fail on the action, reversing the order provides an "early exit" that can speed up non-matching evaluations by ~80%.
**Action:** Always prioritize low-cost boolean or membership checks (like action lookups) before high-cost operations (like regex or glob matching) in hot-path evaluation logic.

## 2026-04-10 - [Inlining Logic in MemoryBackend Batch Operations]
**Learning:** Inlining `get` and `set` logic within `mget` and `mset` methods of an in-memory cache backend significantly reduces performance overhead. This improvement comes from two sources: avoiding the creation and awaiting of individual coroutines for every key in the batch, and reducing the number of calls to `time.monotonic()` (and other redundant calculations) by performing them once per batch.
**Action:** For performance-critical batch operations in synchronous or asynchronous in-memory stores, avoid simple loops that delegate to individual item handlers. Instead, inline the core logic to minimize call stack depth, coroutine overhead, and redundant system calls.

## 2026-04-18 - [Optimizing the Plugin Call Path by Removing State Transitions]
**Learning:** Using a state machine to track transient states (like `RUNNING`) in the hot path of an asynchronous application can be extremely expensive and counterproductive. In XCore, the `RUNNING` state in the `LifecycleManager` not only added ~10-20µs of overhead per call (due to dictionary lookups and state validation) but also acted as an unintended "single-concurrency" lock, causing concurrent calls to fail with an `InvalidTransition` error.
**Action:** Remove transient states that don't represent a persistent lifecycle phase from high-frequency execution paths. Bypassing state machine transitions in the plugin `call` path reduced per-call overhead by ~90% and enabled full concurrency.
