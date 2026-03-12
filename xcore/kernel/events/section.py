
from __future__ import annotations
from enum import Enum
from typing import Any, Callable, NamedTuple, Optional, Dict


from dataclasses import dataclass, field
from typing import Any

@dataclass
class Event:
    name: str
    payload: dict
    source: str | None = None

    propagate: bool = True
    cancelled: bool = False

    # compat legacy
    metadata: dict | None = None
    stop_propagation: bool = False

    def stop(self):
        """Stop propagation of the event."""
        self.propagate = False
        self.stop_propagation = True

    def cancel(self):
        """Cancel the event entirely."""
        self.cancelled = True
        self.stop()

@dataclass
class _HandlerEntry:
    handler: Callable
    priority: int = 50
    once: bool = False
    name: str = ""


@dataclass
class HookResult:
    """Hooks results"""

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
