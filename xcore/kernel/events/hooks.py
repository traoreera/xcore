"""
hooks.py — HookManager v2 (repris de hooks/hooks.py v1).
Conserve toutes les fonctionnalités (wildcards, priorités, intercepteurs,
métriques) mais intégré dans le kernel/events.
"""
from __future__ import annotations

import asyncio
import fnmatch
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple
from enum import Enum

logger = logging.getLogger("xcore.events.hooks")


class HookError(Exception): pass
class HookTimeoutError(HookError): pass


@dataclass
class Event:
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    stop_propagation: bool = False

    def cancel(self) -> None: self.cancelled = True
    def stop(self) -> None: self.stop_propagation = True


@dataclass
class HookResult:
    hook_name: str
    event_name: str
    result: Any = None
    error: Optional[Exception] = None
    execution_time_ms: float = 0.0
    cancelled: bool = False
    skipped: bool = False

    @property
    def success(self) -> bool:
        return self.error is None and not self.cancelled and not self.skipped


class HookInfo(NamedTuple):
    func: Callable
    priority: int
    once: bool
    timeout: Optional[float]
    created_at: float


class InterceptorResult(Enum):
    CONTINUE = "continue"
    SKIP = "skip"
    CANCEL = "cancel"


class HookManager:
    """
    Hook manager avec wildcards, priorités, intercepteurs et métriques.
    Identique à la v1 mais relocalisé dans kernel/events.
    """

    def __init__(self):
        self._hooks: Dict[str, List[HookInfo]] = {}
        self._pre_interceptors: Dict[str, List[Tuple[Callable, int]]] = {}
        self._post_interceptors: Dict[str, List[Tuple[Callable, int]]] = {}
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._result_processors: Dict[str, List[Callable]] = {}

    def register(self, event_name: str, func: Callable, priority: int = 50,
                 once: bool = False, timeout: Optional[float] = None) -> Callable:
        if event_name not in self._hooks:
            self._hooks[event_name] = []
        hook_info = HookInfo(func=func, priority=priority, once=once,
                             timeout=timeout, created_at=time.time())
        idx = 0
        for i, existing in enumerate(self._hooks[event_name]):
            if priority < existing.priority:
                idx = i; break
            idx = i + 1
        self._hooks[event_name].insert(idx, hook_info)
        return func

    def on(self, event_name: str, priority: int = 50, once: bool = False,
           timeout: Optional[float] = None) -> Callable:
        def wrapper(func: Callable) -> Callable:
            self.register(event_name, func, priority, once, timeout)
            return func
        return wrapper

    def once(self, event_name: str, priority: int = 50, timeout: Optional[float] = None) -> Callable:
        return self.on(event_name, priority=priority, once=True, timeout=timeout)

    def unregister(self, event_name: str, func: Callable) -> bool:
        if event_name not in self._hooks:
            return False
        for i, h in enumerate(self._hooks[event_name]):
            if h.func is func:
                self._hooks[event_name].pop(i)
                return True
        return False

    def _get_matching_hooks(self, event_name: str) -> List[Tuple[str, HookInfo]]:
        matching = []
        for pattern, hooks in self._hooks.items():
            if fnmatch.fnmatch(event_name, pattern):
                for hook in hooks:
                    matching.append((pattern, hook))
        matching.sort(key=lambda x: x[1].priority)
        return matching

    async def _execute_single_hook(self, hook_info: HookInfo, event: Event, pattern: str) -> HookResult:
        start = time.time()
        hook_name = hook_info.func.__name__
        try:
            if event.cancelled:
                return HookResult(hook_name=hook_name, event_name=event.name, cancelled=True)
            if hook_info.timeout:
                if inspect.iscoroutinefunction(hook_info.func):
                    result = await asyncio.wait_for(hook_info.func(event), timeout=hook_info.timeout)
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(hook_info.func, event), timeout=hook_info.timeout)
            else:
                if inspect.iscoroutinefunction(hook_info.func):
                    result = await hook_info.func(event)
                else:
                    result = await asyncio.to_thread(hook_info.func, event)
            return HookResult(hook_name=hook_name, event_name=event.name,
                              result=result, execution_time_ms=(time.time()-start)*1000)
        except Exception as e:
            return HookResult(hook_name=hook_name, event_name=event.name,
                              error=e, execution_time_ms=(time.time()-start)*1000)

    async def emit(self, event_name: str, data: Optional[Dict[str, Any]] = None,
                   **kwargs) -> List[HookResult]:
        event = Event(name=event_name, data={**(data or {}), **kwargs})
        matching = self._get_matching_hooks(event_name)
        if not matching:
            return []

        results: List[HookResult] = []
        to_remove: List[Tuple[str, Callable]] = []

        for pattern, hook_info in matching:
            if event.stop_propagation:
                break
            result = await self._execute_single_hook(hook_info, event, pattern)
            results.append(result)
            if hook_info.once:
                to_remove.append((pattern, hook_info.func))

        for pattern, func in to_remove:
            self.unregister(pattern, func)

        self._update_metrics(event_name, results)
        return results

    def _update_metrics(self, event_name: str, results: List[HookResult]) -> None:
        if event_name not in self._metrics:
            self._metrics[event_name] = {
                "total_emissions": 0, "total_hooks_executed": 0,
                "total_errors": 0, "total_time_ms": 0.0, "avg_execution_time_ms": 0.0,
            }
        m = self._metrics[event_name]
        m["total_emissions"] += 1
        m["total_hooks_executed"] += len(results)
        m["total_errors"] += sum(1 for r in results if r.error)
        m["total_time_ms"] += sum(r.execution_time_ms for r in results)
        m["avg_execution_time_ms"] = (
            m["total_time_ms"] / m["total_hooks_executed"]
            if m["total_hooks_executed"] > 0 else 0.0
        )

    def get_metrics(self, event_name: str | None = None) -> Dict[str, Any]:
        return self._metrics.get(event_name, {}) if event_name else self._metrics.copy()

    def list_hooks(self, event_name: str | None = None) -> Dict[str, List]:
        if event_name:
            return {p: [{"name": h.func.__name__, "priority": h.priority, "once": h.once}
                        for h in hooks]
                    for p, hooks in self._hooks.items()
                    if fnmatch.fnmatch(p, event_name) or fnmatch.fnmatch(event_name, p)}
        return {evt: [{"name": h.func.__name__, "priority": h.priority, "once": h.once}
                      for h in hooks]
                for evt, hooks in self._hooks.items()}

    def clear(self, event_name: str | None = None) -> None:
        if event_name:
            self._hooks.pop(event_name, None)
        else:
            self._hooks.clear()
            self._pre_interceptors.clear()
            self._post_interceptors.clear()
            self._result_processors.clear()
            self._metrics.clear()
