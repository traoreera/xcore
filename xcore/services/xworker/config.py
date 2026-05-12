from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkerConfig:
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"
    concurrency: int = 4
    task_soft_time_limit: int = 300
    task_time_limit: int = 360
    broker_connection_retry_on_startup: bool = True
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: list[str] = field(default_factory=lambda: ["json"])
    result_expires: int = 86400
    queues: list[str] = field(default_factory=lambda: ["default"])
    modules: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkerConfig":
        # type: ignore[attr-defined]
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid})
