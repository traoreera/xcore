"""
Dataclasses typées pour chaque section de xcore.yaml.
Toutes ont des valeurs par défaut : zéro config = zéro crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppConfig:
    name: str = "xcore-app"
    env: str = "development"  # development | staging | production
    debug: bool = False
    secret_key: bytes = b"change-me-in-production"
    plugin_prefix: str = "/plugin"
    plugin_tags: list[str] = field(default_factory=list)
    server_key: bytes | str = b"change-me-in-production"
    server_key_iterations: int = 100_000


@dataclass
class DatabaseConfig:
    name: str = "default"
    type: str = "sqlite"
    url: str = "sqlite:///./xcore.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False
    database: str | None = None  # MongoDB
    max_connections: int | None = None  # Redis


@dataclass
class WorkerConfig:
    enabled: bool = False
    name: str = "App"
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"
    task_default_queue: str = "default"
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
        valid = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in valid})

    def to_payload(self) -> dict[str, Any]:
        return {
            "broker_url": self.broker_url,
            "result_backend": self.result_backend,
            "concurrency": self.concurrency,
            "task_soft_time_limit": self.task_soft_time_limit,
            "task_time_limit": self.task_time_limit,
            "broker_connection_retry_on_startup": self.broker_connection_retry_on_startup,
            "task_serializer": self.task_serializer,
            "result_serializer": self.result_serializer,
            "accept_content": self.accept_content,
            "result_expires": self.result_expires,
            "task_queues": self.queues,
            "task_default_queue": self.task_default_queue,
        }


@dataclass
class CacheConfig:
    backend: str = "memory"  # memory | redis
    ttl: int = 300
    max_size: int = 1000
    url: str | None = None


@dataclass
class SchedulerConfig:
    enabled: bool = True
    backend: str = "memory"  # memory | redis | database
    timezone: str = "UTC"
    jobs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ServicesConfig:
    databases: dict[str, DatabaseConfig] = field(default_factory=dict)
    cache: CacheConfig = field(default_factory=CacheConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    extensions: dict[str, dict[str, Any]] = field(default_factory=dict)
    xworker: WorkerConfig = field(default_factory=WorkerConfig)
    celery: WorkerConfig | None = None

    def __post_init__(self) -> None:
        if self.celery and not self.xworker.enabled:
            self.xworker = self.celery


@dataclass
class PluginConfig:
    directory: str = "./plugins"
    secret_key: bytes = b"change-me-in-production"
    strict_trusted: bool = False
    interval: int = 2  # watcher interval (secondes)
    entry_point: str = "src/main.py"
    snapshot: dict[str, Any] = field(
        default_factory=lambda: {
            "extensions": [".log", ".pyc", ".html"],
            "filenames": ["__pycache__", "__init__.py", ".env"],
            "hidden": True,
        }
    )


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: str | None = None
    max_bytes: int = 10_485_760
    backup_count: int = 5


@dataclass
class MetricsConfig:
    enabled: bool = False
    backend: str = "memory"  # memory | prometheus | statsd
    prefix: str = "xcore"


@dataclass
class TracingConfig:
    enabled: bool = False
    backend: str = "noop"  # noop | opentelemetry | jaeger
    service_name: str = "xcore"
    endpoint: str | None = None


@dataclass
class ObservabilityConfig:
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)


@dataclass
class SecurityConfig:
    allowed_imports: list[str] = field(default_factory=list)
    forbidden_imports: list[str] = field(default_factory=list)
    rate_limit_default: dict[str, Any] = field(
        default_factory=lambda: {"calls": 100, "period_seconds": 60}
    )


@dataclass
class MarketplaceConfig:
    """
    Configuration du client marketplace.

    Dans xcore.yaml :
        marketplace:
          url: https://marketplace.xcore.dev
          api_key: ${XCORE_MARKETPLACE_KEY}
          timeout: 10
          cache_ttl: 300
    """

    url: str = "https://marketplace.xcore.dev"
    api_key: str = ""
    timeout: int = 10
    cache_ttl: int = 300


@dataclass
class XcoreConfig:
    app: AppConfig = field(default_factory=AppConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    services: ServicesConfig = field(default_factory=ServicesConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    marketplace: MarketplaceConfig = field(default_factory=MarketplaceConfig)
    raw: dict[str, Any] = field(default_factory=dict)
