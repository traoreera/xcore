"""
Professional Hook System for xcore

Provides an event-driven architecture with support for:
- Priority-based hook execution
- Wildcard pattern matching
- One-time hooks
- Pre/post middleware (interceptors)
- Execution timeouts
- Performance metrics
- Result filtering pipelines
"""

from .hooks import Event, HookError, HookManager, HookResult, HookTimeoutError

__all__ = [
    "HookManager",
    "Event",
    "HookError",
    "HookTimeoutError",
    "HookResult",
]
