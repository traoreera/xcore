## 2025-03-04 - [Optimization of EventBus dispatch overhead]
**Learning:** `inspect.iscoroutinefunction` is surprisingly expensive when called in hot paths like event emission or permission checks (~30x slower than a boolean check). Furthermore, creating per-emission wrapper coroutines for synchronous handlers significantly increases dispatch latency and GC pressure.
**Action:** Always pre-calculate and cache the `is_async` status of callable handlers during the registration/subscription phase. In emission loops, use this cached flag to branch between direct calls and `await` calls to minimize overhead.

## 2025-05-14 - [Memoization in Permission Evaluation]
**Learning:** Permission evaluation involving glob patterns (via `fnmatch`) is computationally expensive, especially when performed on every plugin call. In XCore, this was consuming ~53µs per call set (multiple resources/actions).
**Action:** Implement a memoization layer (simple dictionary cache) for permission check results. This reduced evaluation time by ~70%, bringing it down to ~16µs. Always invalidate the cache when underlying policies are modified.

## 2025-05-15 - [Optimization of Permission Matching Order]
**Learning:** Reordering conditional checks can provide significant performance gains by short-circuiting expensive operations. In `Policy.matches`, checking for action list membership before performing `fnmatch.fnmatch` on resources avoids costly regex-based glob matching in cases where the action is already a mismatch.
**Action:** Always prioritize simple, constant-time, or low-overhead checks (like list membership or boolean flags) before more computationally intensive operations (like glob matching or regex) in multi-condition evaluations. This simple reordering in `Policy.matches` yielded a ~80% speedup for mismatching actions.
