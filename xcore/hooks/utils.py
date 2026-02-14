"""
Utility functions and helpers for the hook system.

Provides common interceptors, result processors, and helper decorators.
"""

import asyncio
import inspect
import time
from functools import wraps
from typing import Callable, List, Optional

from .hooks import Event, HookManager, HookResult, InterceptorResult


def logging_interceptor(log_level: str = "info") -> Callable:
    """
    Create an interceptor that logs event emissions.

    Args:
        log_level: Logging level (debug, info, warning, error)

    Example:
        hooks.add_pre_interceptor("*", logging_interceptor("debug"))
    """
    import logging

    logger = logging.getLogger("hooks.interceptor")

    async def interceptor(event: Event) -> InterceptorResult:
        log_func = getattr(logger, log_level.lower(), logger.info)
        log_func(
            f"Event emitted: {event.name} with data keys: {list(event.data.keys())}"
        )
        return InterceptorResult.CONTINUE

    return interceptor


def rate_limit_interceptor(max_calls: int, window_seconds: float) -> Callable:
    """
    Create an interceptor that rate-limits event emissions.

    Args:
        max_calls: Maximum number of calls allowed in the window
        window_seconds: Time window in seconds

    Example:
        hooks.add_pre_interceptor("api.request", rate_limit_interceptor(100, 60.0))
    """
    calls = []

    async def interceptor(event: Event) -> InterceptorResult:
        now = time.time()

        # Remove old calls outside the window
        calls[:] = [c for c in calls if now - c < window_seconds]

        if len(calls) >= max_calls:
            return InterceptorResult.CANCEL

        calls.append(now)
        return InterceptorResult.CONTINUE

    return interceptor


def debounce_interceptor(delay_seconds: float) -> Callable:
    """
    Create an interceptor that debounces event emissions.

    Only the last event in the delay window will be processed.

    Args:
        delay_seconds: Debounce delay in seconds
    """
    last_emission = 0.0
    pending_task = None

    async def interceptor(event: Event) -> InterceptorResult:
        nonlocal last_emission, pending_task

        now = time.time()

        if now - last_emission < delay_seconds:
            # Cancel this emission
            return InterceptorResult.CANCEL

        last_emission = now
        return InterceptorResult.CONTINUE

    return interceptor


def validation_interceptor(required_keys: List[str]) -> Callable:
    """
    Create an interceptor that validates event data has required keys.

    Args:
        required_keys: List of required data keys

    Example:
        hooks.add_pre_interceptor("user.created", validation_interceptor(["user_id", "email"]))
    """
    import logging

    logger = logging.getLogger("hooks.validation")

    async def interceptor(event: Event) -> InterceptorResult:
        missing = [key for key in required_keys if key not in event.data]
        if missing:
            logger.error(f"Event {event.name} missing required keys: {missing}")
            return InterceptorResult.CANCEL
        return InterceptorResult.CONTINUE

    return interceptor


def error_counting_processor(max_errors: int = 10) -> Callable:
    """
    Create a result processor that counts errors and logs warnings.

    Args:
        max_errors: Maximum errors before logging a critical warning
    """
    import logging

    logger = logging.getLogger("hooks.processor")
    error_counts = {}

    def processor(results: List[HookResult]) -> List[HookResult]:
        errors = [r for r in results if r.error is not None]

        for result in errors:
            key = f"{result.event_name}:{result.hook_name}"
            error_counts[key] = error_counts.get(key, 0) + 1

            if error_counts[key] >= max_errors:
                logger.critical(
                    f"Hook {result.hook_name} for {result.event_name} "
                    f"has failed {error_counts[key]} times: {result.error}"
                )
            else:
                logger.warning(
                    f"Hook {result.hook_name} failed for {result.event_name}: {result.error}"
                )

        return results

    return processor


def result_filter_processor(success_only: bool = False) -> Callable:
    """
    Create a result processor that filters results.

    Args:
        success_only: If True, only keep successful results
    """

    def processor(results: List[HookResult]) -> List[HookResult]:
        return [r for r in results if r.success] if success_only else results
    return processor


def timing_processor(threshold_ms: float = 1000.0) -> Callable:
    """
    Create a result processor that logs slow hooks.

    Args:
        threshold_ms: Threshold in milliseconds for slow hook warning
    """
    import logging

    logger = logging.getLogger("hooks.timing")

    def processor(results: List[HookResult]) -> List[HookResult]:
        for result in results:
            if result.execution_time_ms > threshold_ms:
                logger.warning(
                    f"Slow hook detected: {result.hook_name} for {result.event_name} "
                    f"took {result.execution_time_ms:.2f}ms (threshold: {threshold_ms}ms)"
                )
        return results

    return processor


class HookChain:
    """
    Helper class for creating chains of hooks that depend on each other.

    Example:
        chain = HookChain(hooks, "data.process")
        chain.then(validate_data, priority=10)
        chain.then(transform_data, priority=20)
        chain.then(save_data, priority=30)
    """

    def __init__(self, hook_manager: HookManager, event_name: str):
        self.hooks = hook_manager
        self.event_name = event_name
        self._current_priority = 50

    def then(self, func: Callable, priority: Optional[int] = None) -> "HookChain":
        """
        Add a hook to the chain.

        Args:
            func: The hook function
            priority: Priority (defaults to incrementing from 50)

        Returns:
            Self for chaining
        """
        if priority is None:
            priority = self._current_priority
            self._current_priority += 10

        self.hooks.on(self.event_name, priority=priority)(func)
        return self


class ConditionalHook:
    """
    Decorator for conditionally executing hooks based on event data.

    Example:
        @ConditionalHook(lambda e: e.data.get("environment") == "production")
        @hooks.on("app.startup")
        async def production_only_task(event: Event):
            await setup_production_services()
    """

    def __init__(self, condition: Callable[[Event], bool]):
        self.condition = condition

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(event: Event):
            if not self.condition(event):
                return None
            return (
                await func(event) if asyncio.iscoroutinefunction(func) else func(event)
            )

        return wrapper


def retry_hook(max_retries: int = 3, delay_seconds: float = 1.0) -> Callable:
    """
    Decorator that adds retry logic to a hook.

    Args:
        max_retries: Maximum number of retry attempts
        delay_seconds: Delay between retries

    Example:
        @retry_hook(max_retries=3, delay_seconds=2.0)
        @hooks.on("api.call")
        async def unreliable_api_call(event: Event):
            return await call_external_api()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(event: Event):
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(event) if inspect.iscoroutinefunction(func) else func(event)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        # Exponential backoff
                        await asyncio.sleep(delay_seconds * (attempt + 1))
                    else:
                        raise last_error

        return wrapper

    return decorator


def memoized_hook(ttl_seconds: float = 300.0) -> Callable:
    """
    Decorator that caches hook results for a time period.

    Args:
        ttl_seconds: Time-to-live for cached results

    Example:
        @memoized_hook(ttl_seconds=60.0)
        @hooks.on("data.fetch")
        async def expensive_data_fetch(event: Event):
            return await fetch_from_slow_source()
    """
    cache = {}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(event: Event):
            # Create cache key from event name and data
            cache_key = (event.name, frozenset(event.data.items()))

            now = time.time()
            if cache_key in cache:
                result, expiry = cache[cache_key]
                if now < expiry:
                    return result

            result = (
                await func(event) if asyncio.iscoroutinefunction(func) else func(event)
            )
            cache[cache_key] = (result, now + ttl_seconds)
            return result

        return wrapper

    return decorator
