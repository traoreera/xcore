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

## 2026-04-20 - [Optimizing Plugin Call Path & Concurrency]
**Learning:** Using a formal state machine with `READY` -> `RUNNING` -> `READY` transitions for every plugin call introduces significant overhead (~10µs per call) and, more importantly, prevents concurrency because the state machine enforces sequential transitions.
**Action:** Remove transitional states (like `RUNNING`) from the high-frequency call path. Replace expensive state transitions with a fast boolean check (`is_available`) to ensure the plugin is `READY` before execution. This enables concurrent plugin calls and reduces per-call overhead by ~90% (to ~0.8µs).

## 2026-05-10 - [Synchronous Rate Limiting in Hot-Path]
**Learning:** Using `async` methods and `asyncio.Lock` for purely in-memory rate limiting operations in the plugin call hot-path introduces significant coroutine scheduling and locking overhead (~0.2s for 100k calls). Since `asyncio` is single-threaded, fast in-memory operations are effectively atomic if they don't contain `await` points, making the lock redundant.
**Action:** Convert in-memory rate limiters and similar hot-path components to synchronous methods without locks to eliminate `asyncio` overhead. This yielded a ~55% performance gain in the rate-limiting check.
