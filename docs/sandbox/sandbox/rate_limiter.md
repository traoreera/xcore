```markdown
## Rate Limiter

**Overview:** The `rate_limiter.py` file provides a rate limiting system within the XCore platform. It's designed to prevent abuse of resources by controlling the frequency of requests, ensuring fair usage and preventing service overload. This module operates on a per-plugin basis, offering granular control over request rates for individual services.

**Responsibilities:**
This file is responsible for:
*   Enforcing rate limits on incoming requests.
*   Providing a mechanism to track and manage request frequency.
*   Preventing excessive usage that could negatively impact system performance or availability.

**Key Components:**

*   `RateLimiter`: This class is the core of the rate limiting functionality. It utilizes a sliding window algorithm (implemented with `collections.deque`) to monitor requests and enforce configured limits. The `check()` method determines if a request should be allowed based on its timing relative to the last permitted request.  It also provides a `stats()` method for retrieving current statistics.
*   `RateLimitExceeded`: This exception is raised when a request exceeds the defined rate limit, signaling that the request must be rejected or handled differently.
*   `RateLimiterRegistry`: This registry manages instances of `RateLimiter`, associating each with its corresponding plugin name.  This allows for efficient lookup and invocation of the rate limiter based on the calling plugin's identifier.

**Dependencies:**

*   `asyncio`: Provides asynchronous programming capabilities, crucial for handling concurrent requests efficiently and managing locks safely within the rate limiting process.
*   `collections.deque`: Used to implement the sliding window algorithm, providing efficient insertion and deletion of elements from both ends.
*   `time`: Utilized for obtaining monotonic timestamps, ensuring accurate timing even if the system clock is adjusted. This prevents issues with rate limiting based on wall-clock time.
*   `RateLimitConfig`: A configuration object that defines the parameters for each rate limit, including the `period_seconds` (the duration of the window) and the maximum number of `calls` allowed within that period.

**How It Fits In:**

The `RateLimiterRegistry` is invoked by other modules within the XCore codebase during request processing. Specifically, the `check()` method of the registry is called before a request can proceed to ensure it doesn't violate rate limits. The `check()` method then utilizes the appropriate `RateLimiter` instance based on the plugin name.  The `RateLimiter`’s internal sliding window algorithm determines whether the request should be allowed or if a `RateLimitExceeded` exception is raised. The registry also provides a `stats()` method for monitoring and debugging rate limiting behavior. This module integrates seamlessly into XCore, providing a robust mechanism for managing request rates across various components.
```