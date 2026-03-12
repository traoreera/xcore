
from __future__ import annotations
from enum import Enum
from typing import Any, Callable, NamedTuple, Optional


from dataclasses import dataclass, field
from typing import Any

@dataclass
class Event:
    """Évent struct for handlers."""

    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    propagate: bool = True
    cancelled: bool = False

    def stop(self) -> None:
        self.propagate = False

    def cancel(self) -> None:
        self.cancelled = True


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
