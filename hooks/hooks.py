"""
Professional Hook System for xcore

A production-grade event system supporting:
- Async/sync hook execution with priority ordering
- Wildcard pattern matching for event names
- One-time hooks (auto-cleanup after execution)
- Pre/post middleware (interceptors)
- Execution timeouts
- Performance metrics and monitoring
- Result filtering and processing pipelines
"""

import asyncio
import fnmatch
import inspect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
)

logger = logging.getLogger(__name__)


class HookError(Exception):
    """Base exception for hook-related errors."""



class HookTimeoutError(HookError):
    """Raised when a hook execution exceeds its timeout."""



class HookCancelledError(HookError):
    """Raised when a hook is cancelled (e.g., by middleware)."""



@dataclass
class Event:
    """Structured event data passed to hooks."""

    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    stop_propagation: bool = False

    def cancel(self) -> None:
        """Cancel this event (prevents further hook execution)."""
        self.cancelled = True

    def stop(self) -> None:
        """Stop event propagation to remaining hooks."""
        self.stop_propagation = True


@dataclass
class HookResult:
    """Result of a single hook execution."""

    hook_name: str
    event_name: str
    result: Any = None
    error: Optional[Exception] = None
    execution_time_ms: float = 0.0
    cancelled: bool = False
    skipped: bool = False

    @property
    def success(self) -> bool:
        """Check if hook executed successfully."""
        return self.error is None and not self.cancelled and not self.skipped


class HookInfo(NamedTuple):
    """Information about a registered hook."""

    func: Callable
    priority: int
    once: bool
    timeout: Optional[float]
    created_at: float


class InterceptorResult(Enum):
    """Result of interceptor execution."""

    CONTINUE = "continue"
    SKIP = "skip"
    CANCEL = "cancel"


class HookManager:
    """
        Professional event hook manager for xcore.

        Features:
        - Priority-based async/sync hook execution
        - Wildcard pattern matching (e.g., "plugin.*", "*.update")
        - One-time hooks with auto-cleanup
        - Pre/post middleware (interceptors)
        - Execution timeouts
        - Performance metrics
        - Result filtering pipelines

        Example:
    ```python
            hooks = HookManager()

            # Basic usage
            @hooks.on("user.created")
            async def on_user_created(event: Event):
                await send_welcome_email(event.data["user"])

            # With priority (lower = earlier)
            @hooks.on("user.created", priority=10)
            async def log_user_creation(event: Event):
                logger.info(f"User created: {event.data['user'].id}")

            # One-time hook
            @hooks.once("server.startup")
            async def init_service(event: Event):
                await initialize_service()

            # Wildcard pattern
            @hooks.on("plugin.*.loaded")
            async def on_any_plugin_loaded(event: Event):
                logger.info(f"Plugin loaded: {event.name}")

            # Emit event
            await hooks.emit("user.created", Event("user.created", data={"user": user}))```
    """

    def __init__(self):
        # event_name -> list of HookInfo
        self._hooks: Dict[str, List[HookInfo]] = {}
        # Pre-interceptors: event_name -> list of (func, priority)
        self._pre_interceptors: Dict[str, List[Tuple[Callable, int]]] = {}
        # Post-interceptors: event_name -> list of (func, priority)
        self._post_interceptors: Dict[str, List[Tuple[Callable, int]]] = {}
        # Performance metrics
        self._metrics: Dict[str, Dict[str, Any]] = {}
        # Result processors: event_name -> list of processors
        self._result_processors: Dict[
            str, List[Callable[[List[HookResult]], List[HookResult]]]
        ] = {}

    def register(
        self,
        event_name: str,
        func: Callable,
        priority: int = 50,
        once: bool = False,
        timeout: Optional[float] = None,
    ) -> Callable:
        """
        Register a hook for an event.

        Args:
            event_name: Event name or wildcard pattern (e.g., "plugin.*")
            func: Callback function (sync or async)
            priority: Execution priority (0-100, lower = earlier)
            once: If True, auto-unregister after first execution
            timeout: Maximum execution time in seconds (None = no limit)

        Returns:
            The registered function (for use as decorator)
        """
        if event_name not in self._hooks:
            self._hooks[event_name] = []

        hook_info = HookInfo(
            func=func,
            priority=priority,
            once=once,
            timeout=timeout,
            created_at=time.time(),
        )

        # Insert sorted by priority
        idx = 0
        for i, existing in enumerate(self._hooks[event_name]):
            if priority < existing.priority:
                idx = i
                break
            idx = i + 1

        self._hooks[event_name].insert(idx, hook_info)
        logger.debug(
            f"Hook registered: {event_name} -> {func.__name__} (priority: {priority}, once: {once})"
        )
        return func

    def on(
        self,
        event_name: str,
        priority: int = 50,
        once: bool = False,
        timeout: Optional[float] = None,
    ):
        """
        Decorator to register a hook.

        Args:
            event_name: Event name or wildcard pattern
            priority: Execution priority (0-100, lower = earlier)
            once: Auto-unregister after first execution
            timeout: Maximum execution time in seconds

        Example:
            @hooks.on("user.created", priority=10)
            async def notify_user(event: Event):
                await send_notification(event.data["user"])
        """

        def wrapper(func: Callable) -> Callable:
            self.register(event_name, func, priority, once, timeout)
            return func

        return wrapper

    def once(
        self, event_name: str, priority: int = 50, timeout: Optional[float] = None
    ):
        """
        Decorator to register a one-time hook.

        The hook automatically unregisters after its first execution.

        Example:
            @hooks.once("server.startup")
            async def initialize(event: Event):
                await setup_service()
        """
        return self.on(event_name, priority=priority, once=True, timeout=timeout)

    def unregister(self, event_name: str, func: Callable) -> bool:
        """
        Unregister a specific hook.

        Args:
            event_name: Event name the hook was registered for
            func: Function to unregister

        Returns:
            True if hook was found and removed, False otherwise
        """
        if event_name not in self._hooks:
            return False

        for i, hook_info in enumerate(self._hooks[event_name]):
            if hook_info.func is func:
                self._hooks[event_name].pop(i)
                logger.debug(f"Hook unregistered: {event_name} -> {func.__name__}")
                return True

        return False

    def add_pre_interceptor(
        self, event_name: str, func: Callable, priority: int = 50
    ) -> Callable:
        """
        Add a pre-execution interceptor (middleware).

        Interceptors are called before hooks and can:
        - Modify the event data
        - Skip hook execution
        - Cancel the entire event

        Args:
            event_name: Event name or pattern
            func: Interceptor function receiving (event) returning InterceptorResult
            priority: Execution priority

        Returns:
            The interceptor function
        """
        if event_name not in self._pre_interceptors:
            self._pre_interceptors[event_name] = []

        # Insert sorted by priority
        idx = 0
        for i, (_, p) in enumerate(self._pre_interceptors[event_name]):
            if priority < p:
                idx = i
                break
            idx = i + 1

        self._pre_interceptors[event_name].insert(idx, (func, priority))
        logger.debug(f"Pre-interceptor added: {event_name} -> {func.__name__}")
        return func

    def add_post_interceptor(
        self, event_name: str, func: Callable, priority: int = 50
    ) -> Callable:
        """
        Add a post-execution interceptor.

        Called after all hooks have executed. Can modify results.

        Args:
            event_name: Event name or pattern
            func: Interceptor function receiving (event, results)
            priority: Execution priority

        Returns:
            The interceptor function
        """
        if event_name not in self._post_interceptors:
            self._post_interceptors[event_name] = []

        idx = 0
        for i, (_, p) in enumerate(self._post_interceptors[event_name]):
            if priority < p:
                idx = i
                break
            idx = i + 1

        self._post_interceptors[event_name].insert(idx, (func, priority))
        logger.debug(f"Post-interceptor added: {event_name} -> {func.__name__}")
        return func

    def add_result_processor(
        self, event_name: str, processor: Callable[[List[HookResult]], List[HookResult]]
    ) -> None:
        """
        Add a result processor for an event.

        Processors can filter, transform, or aggregate hook results.

        Args:
            event_name: Event name or pattern
            processor: Function receiving and returning List[HookResult]
        """
        if event_name not in self._result_processors:
            self._result_processors[event_name] = []
        self._result_processors[event_name].append(processor)

    def _get_matching_hooks(self, event_name: str) -> List[Tuple[str, HookInfo]]:
        """Get all hooks matching an event name (including wildcards)."""
        matching = []

        for registered_pattern, hooks in self._hooks.items():
            if fnmatch.fnmatch(event_name, registered_pattern):
                for hook in hooks:
                    matching.append((registered_pattern, hook))

        # Sort by priority across all patterns
        matching.sort(key=lambda x: x[1].priority)
        return matching

    def _get_matching_interceptors(
        self, event_name: str, interceptors_dict: Dict[str, List]
    ) -> List[Tuple[Callable, int]]:
        """Get all interceptors matching an event name."""
        matching = []

        for pattern, interceptors in interceptors_dict.items():
            if fnmatch.fnmatch(event_name, pattern):
                matching.extend(interceptors)

        # Sort by priority
        matching.sort(key=lambda x: x[1])
        return matching

    async def _run_pre_interceptors(self, event: Event) -> InterceptorResult:
        """Run pre-execution interceptors."""
        interceptors = self._get_matching_interceptors(
            event.name, self._pre_interceptors
        )

        for interceptor, _ in interceptors:
            try:
                if inspect.iscoroutinefunction(interceptor):
                    result = await interceptor(event)
                else:
                    result = interceptor(event)

                if result == InterceptorResult.CANCEL:
                    return InterceptorResult.CANCEL
                elif result == InterceptorResult.SKIP:
                    return InterceptorResult.SKIP
                # CONTINUE proceeds to next interceptor
            except Exception as e:
                logger.error(f"Pre-interceptor error for {event.name}: {e}")
                # Continue with other interceptors

        return InterceptorResult.CONTINUE

    async def _run_post_interceptors(
        self, event: Event, results: List[HookResult]
    ) -> List[HookResult]:
        """Run post-execution interceptors."""
        interceptors = self._get_matching_interceptors(
            event.name, self._post_interceptors
        )

        for interceptor, _ in interceptors:
            try:
                if inspect.iscoroutinefunction(interceptor):
                    results = await interceptor(event, results) or results
                else:
                    results = interceptor(event, results) or results
            except Exception as e:
                logger.error(f"Post-interceptor error for {event.name}: {e}")

        return results

    async def _execute_single_hook(
        self,
        hook_info: HookInfo,
        event: Event,
        pattern: str,
    ) -> HookResult:
        """Execute a single hook with timeout and error handling."""
        start_time = time.time()
        hook_name = hook_info.func.__name__

        try:
            # Check if event was cancelled
            if event.cancelled:
                return HookResult(
                    hook_name=hook_name,
                    event_name=event.name,
                    cancelled=True,
                    execution_time_ms=0.0,
                )

            # Execute with timeout if specified
            if hook_info.timeout:
                try:
                    if inspect.iscoroutinefunction(hook_info.func):
                        result = await asyncio.wait_for(
                            hook_info.func(event), timeout=hook_info.timeout
                        )
                    else:
                        result = await asyncio.wait_for(
                            asyncio.to_thread(hook_info.func, event),
                            timeout=hook_info.timeout,
                        )
                except asyncio.TimeoutError:
                    raise HookTimeoutError(
                        f"Hook {hook_name} exceeded {hook_info.timeout}s timeout"
                    )
            else:
                if inspect.iscoroutinefunction(hook_info.func):
                    result = await hook_info.func(event)
                else:
                    result = await asyncio.to_thread(hook_info.func, event)

            execution_time = (time.time() - start_time) * 1000

            return HookResult(
                hook_name=hook_name,
                event_name=event.name,
                result=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Hook {hook_name} failed for {event.name}: {e}")
            return HookResult(
                hook_name=hook_name,
                event_name=event.name,
                error=e,
                execution_time_ms=execution_time,
            )

    async def emit(
        self, event_name: str, data: Optional[Dict[str, Any]] = None, **kwargs
    ) -> List[HookResult]:
        """
        Emit an event and execute all matching hooks.

        Args:
            event_name: Name of the event to emit
            data: Event data dictionary
            **kwargs: Additional data (merged with data dict)

        Returns:
            List of HookResult objects
        """
        # Merge data and kwargs
        event_data = {**(data or {}), **kwargs}
        event = Event(name=event_name, data=event_data)

        # Run pre-interceptors
        interceptor_result = await self._run_pre_interceptors(event)

        if interceptor_result == InterceptorResult.CANCEL:
            return [
                HookResult(
                    hook_name="__interceptor__",
                    event_name=event_name,
                    cancelled=True,
                )
            ]

        if interceptor_result == InterceptorResult.SKIP:
            return []

        # Get matching hooks
        matching_hooks = self._get_matching_hooks(event_name)

        if not matching_hooks:
            logger.debug(f"No hooks for event: {event_name}")
            return []

        # Execute hooks
        results: List[HookResult] = []
        hooks_to_remove: List[Tuple[str, Callable]] = []

        for pattern, hook_info in matching_hooks:
            # Check if propagation was stopped
            if event.stop_propagation:
                break

            result = await self._execute_single_hook(hook_info, event, pattern)
            results.append(result)

            # Track one-time hooks for removal
            if hook_info.once:
                hooks_to_remove.append((pattern, hook_info.func))

        # Remove one-time hooks
        for pattern, func in hooks_to_remove:
            self.unregister(pattern, func)

        # Run post-interceptors
        results = await self._run_post_interceptors(event, results)

        # Apply result processors
        for processor_pattern, processors in self._result_processors.items():
            if fnmatch.fnmatch(event_name, processor_pattern):
                for processor in processors:
                    try:
                        results = processor(results)
                    except Exception as e:
                        logger.error(f"Result processor error for {event_name}: {e}")

        # Update metrics
        self._update_metrics(event_name, results)

        return results

    async def emit_until_first(
        self, event_name: str, data: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[Any]:
        """
        Emit event and return the first non-None result.

        Args:
            event_name: Name of the event
            data: Event data
            **kwargs: Additional data

        Returns:
            First non-None result from hooks, or None
        """
        results = await self.emit(event_name, data, **kwargs)
        for result in results:
            if result.success and result.result is not None:
                return result.result
        return None

    async def emit_until_success(
        self, event_name: str, data: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Optional[HookResult]:
        """
        Emit event and return the first successful result.

        Args:
            event_name: Name of the event
            data: Event data
            **kwargs: Additional data

        Returns:
            First successful HookResult, or None
        """
        results = await self.emit(event_name, data, **kwargs)
        for result in results:
            if result.success:
                return result
        return None

    def _update_metrics(self, event_name: str, results: List[HookResult]) -> None:
        """Update performance metrics for an event."""
        if event_name not in self._metrics:
            self._metrics[event_name] = {
                "total_emissions": 0,
                "total_hooks_executed": 0,
                "total_errors": 0,
                "total_time_ms": 0.0,
                "avg_execution_time_ms": 0.0,
            }

        metrics = self._metrics[event_name]
        metrics["total_emissions"] += 1
        metrics["total_hooks_executed"] += len(results)
        metrics["total_errors"] += sum(1 for r in results if r.error is not None)
        metrics["total_time_ms"] += sum(r.execution_time_ms for r in results)
        metrics["avg_execution_time_ms"] = (
            metrics["total_time_ms"] / metrics["total_hooks_executed"]
            if metrics["total_hooks_executed"] > 0
            else 0.0
        )

    def get_metrics(self, event_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance metrics for events.

        Args:
            event_name: Specific event name, or None for all metrics

        Returns:
            Metrics dictionary
        """
        if event_name:
            return self._metrics.get(event_name, {})
        return self._metrics.copy()

    def list_hooks(
        self, event_name: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all registered hooks.

        Args:
            event_name: Filter by event name (supports wildcards), or None for all

        Returns:
            Dictionary of event names to hook information
        """
        if event_name:
            result = {}
            for pattern, hooks in self._hooks.items():
                if fnmatch.fnmatch(pattern, event_name) or fnmatch.fnmatch(
                    event_name, pattern
                ):
                    result[pattern] = [
                        {
                            "name": h.func.__name__,
                            "priority": h.priority,
                            "once": h.once,
                            "timeout": h.timeout,
                            "module": h.func.__module__,
                        }
                        for h in hooks
                    ]
            return result

        return {
            evt: [
                {
                    "name": h.func.__name__,
                    "priority": h.priority,
                    "once": h.once,
                    "timeout": h.timeout,
                    "module": h.func.__module__,
                }
                for h in hooks
            ]
            for evt, hooks in self._hooks.items()
        }

    def clear(self, event_name: Optional[str] = None) -> None:
        """
        Clear all hooks for an event or all events.

        Args:
            event_name: Event name to clear, or None to clear all
        """
        if event_name:
            if event_name in self._hooks:
                del self._hooks[event_name]
            # Also clear from patterns
            for pattern in list(self._hooks.keys()):
                if fnmatch.fnmatch(event_name, pattern):
                    del self._hooks[pattern]
        else:
            self._hooks.clear()
            self._pre_interceptors.clear()
            self._post_interceptors.clear()
            self._result_processors.clear()
            self._metrics.clear()

    def decorator(self, event_name: str, priority: int = 50):
        """
        Legacy decorator for backward compatibility.

        Use @hooks.on() for new code.
        """
        return self.on(event_name, priority=priority)


# Backward compatibility alias
EventHookManager = HookManager
