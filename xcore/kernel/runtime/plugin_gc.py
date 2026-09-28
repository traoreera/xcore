"""
plugin_gc.py — Ramasse-miette forcé pour les plugins Trusted.

On ne peut pas se fier à ce qu'un plugin nettoie correctement ce qu'il a
enregistré pendant on_load, dans son `on_unload`/`on_stop` — ces hooks sont
écrits par des auteurs tiers, avec des garanties variables. Ce module
intercepte, au moment où le plugin obtient scheduler/health/events/hooks
via son PluginContext, ce qu'il y enregistre (job scheduler, health check,
abonnement event/hook) — pour pouvoir tout désinscrire de force au unload,
que le plugin l'ait fait proprement ou pas.

Usage (dans LifecycleManager._do_load) :
    tracker = PluginResourceTracker(manifest.name)
    ctx.events = tracker.wrap_events(ctx.events)
    ctx.hooks = tracker.wrap_hooks(ctx.hooks)
    ctx.health = tracker.wrap_health(ctx.health)
    if "scheduler" in ctx.services:
        ctx.services = dict(ctx.services)
        ctx.services["scheduler"] = tracker.wrap_scheduler(ctx.services["scheduler"])

Puis, dans LifecycleManager._do_unload :
    tracker.cleanup()
"""

from __future__ import annotations

import contextlib
from typing import Any, Callable

from ..observability import get_logger

logger = get_logger("xcore.runtime.plugin_gc")


class _ScopedScheduler:
    """Proxy autour de SchedulerService : mémorise les job_id créés par CE plugin."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self._job_ids: set[str] = set()

    def add_job(
        self,
        func: Callable,
        trigger: str = "cron",
        job_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        effective_id = job_id or getattr(func, "__name__", repr(func))
        self._job_ids.add(effective_id)
        return self._real.add_job(func, trigger=trigger, job_id=job_id, **kwargs)

    def cron(self, expression: str, job_id: str | None = None) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._job_ids.add(job_id or fn.__name__)
            return self._real.cron(expression, job_id=job_id)(fn)

        return decorator

    def interval(self, **kwargs: Any) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._job_ids.add(fn.__name__)
            return self._real.interval(**kwargs)(fn)

        return decorator

    def cleanup(self, plugin_name: str) -> None:
        for job_id in self._job_ids:
            with contextlib.suppress(Exception):
                self._real.remove_job(job_id)
        if self._job_ids:
            logger.debug(
                "scheduler jobs released",
                plugin=plugin_name,
                jobs=sorted(self._job_ids),
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class _ScopedHealth:
    """Proxy autour de HealthChecker : mémorise les checks enregistrés par CE plugin."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self._names: set[str] = set()

    def register(self, name: str) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._names.add(name)
            return self._real.register(name)(fn)

        return decorator

    def cleanup(self, plugin_name: str) -> None:
        for name in self._names:
            with contextlib.suppress(Exception):
                self._real.unregister(name)
        if self._names:
            logger.debug(
                "health checks released", plugin=plugin_name, checks=sorted(self._names)
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class _ScopedEvents:
    """Proxy autour de l'EventBus (.on/.subscribe/.once) : mémorise (event_name, handler)."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self._pairs: list[tuple[str, Callable]] = []

    def on(
        self, event_name: str, priority: int = 50, name: str | None = None
    ) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._pairs.append((event_name, fn))
            return self._real.on(event_name, priority=priority, name=name)(fn)

        return decorator

    def once(self, event_name: str, priority: int = 50) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._pairs.append((event_name, fn))
            return self._real.once(event_name, priority=priority)(fn)

        return decorator

    def subscribe(
        self,
        event_name: str,
        handler: Callable,
        priority: int = 50,
        once: bool = False,
        name: str | None = None,
    ) -> None:
        self._pairs.append((event_name, handler))
        self._real.subscribe(
            event_name, handler, priority=priority, once=once, name=name
        )

    def cleanup(self, plugin_name: str) -> None:
        for event_name, handler in self._pairs:
            with contextlib.suppress(Exception):
                self._real.unsubscribe(event_name, handler)
        if self._pairs:
            logger.debug(
                "event subscriptions released",
                plugin=plugin_name,
                count=len(self._pairs),
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class _ScopedHooks:
    """Proxy autour du HookManager (.on/.register/.once) : mémorise (event_name, func)."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self._pairs: list[tuple[str, Callable]] = []

    def register(
        self,
        event_name: str,
        func: Callable,
        priority: int = 50,
        once: bool = False,
        timeout: float | None = None,
    ) -> Callable:
        self._pairs.append((event_name, func))
        return self._real.register(
            event_name, func, priority=priority, once=once, timeout=timeout
        )

    def on(
        self,
        event_name: str,
        priority: int = 50,
        once: bool = False,
        timeout: float | None = None,
    ) -> Callable:
        def wrapper(func: Callable) -> Callable:
            self._pairs.append((event_name, func))
            return self._real.on(
                event_name, priority=priority, once=once, timeout=timeout
            )(func)

        return wrapper

    def once(
        self, event_name: str, priority: int = 50, timeout: float | None = None
    ) -> Callable:
        return self.on(event_name, priority=priority, once=True, timeout=timeout)

    def cleanup(self, plugin_name: str) -> None:
        for event_name, func in self._pairs:
            with contextlib.suppress(Exception):
                self._real.unregister(event_name, func)
        if self._pairs:
            logger.debug("hooks released", plugin=plugin_name, count=len(self._pairs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class PluginResourceTracker:
    """
    Regroupe les proxies de scoping-par-plugin et leur nettoyage forcé au unload.

    Une instance par (re)chargement de plugin — jetée après le cleanup qui
    suit chaque unload/reload.
    """

    def __init__(self, plugin_name: str) -> None:
        self._plugin_name = plugin_name
        self._scoped: list[Any] = []

    def wrap_scheduler(self, real: Any) -> Any:
        if real is None:
            return real
        proxy = _ScopedScheduler(real)
        self._scoped.append(proxy)
        return proxy

    def wrap_health(self, real: Any) -> Any:
        if real is None:
            return real
        proxy = _ScopedHealth(real)
        self._scoped.append(proxy)
        return proxy

    def wrap_events(self, real: Any) -> Any:
        if real is None:
            return real
        proxy = _ScopedEvents(real)
        self._scoped.append(proxy)
        return proxy

    def wrap_hooks(self, real: Any) -> Any:
        if real is None:
            return real
        proxy = _ScopedHooks(real)
        self._scoped.append(proxy)
        return proxy

    def cleanup(self) -> None:
        for proxy in self._scoped:
            proxy.cleanup(self._plugin_name)
        self._scoped.clear()
