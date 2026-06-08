"""
Dataclasses typées pour chaque section de xcore.yaml.
Toutes ont des valeurs par défaut : zéro config = zéro crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class FastAPIConfig:
    """Paramètres passés au constructeur FastAPI()."""

    debug: bool = False
    title: str = "xcore"
    summary: str | None = None
    description: str = "For Plugin Isolation and Orchestration"
    version: str = "0.1.0"
    openapi_url: str | None = "/openapi.json"
    openapi_tags: list[dict[str, Any]] = field(default_factory=list)
    redirect_slashes: bool = True
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    swagger_ui_oauth2_redirect_url: str = "/docs/oauth2-redirect"
    terms_of_service: str | None = None
    contact: dict[str, Any] | None = None
    license_info: dict[str, Any] | None = None
    openapi_prefix: str = ""
    root_path: str = ""
    deprecated: bool = False

    def to_dict(self):
        return {
            "debug": self.debug,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "version": self.version,
            "openapi_url": self.openapi_url,
            "openapi_tags": self.openapi_tags,
            "redirect_slashes": self.redirect_slashes,
            "docs_url": self.docs_url,
            "redoc_url": self.redoc_url,
            "swagger_ui_oauth2_redirect_url": self.swagger_ui_oauth2_redirect_url,
            "terms_of_service": self.terms_of_service,
            "contact": self.contact,
            "license_info": self.license_info,
            "openapi_prefix": self.openapi_prefix,
            "root_path": self.root_path,
            "deprecated": self.deprecated,
        }


@dataclass
class ServerConfig:
    """Paramètres uvicorn pour `xcore worker start api`."""

    app: str = "main:app"
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    log_level: str = "info"
    proxy_headers: bool = True
    forwarded_allow_ips: str = "*"
    lifespan: str = "on"

    def to_dict(self):
        return {
            "app": self.app,
            "host": self.host,
            "port": self.port,
            "workers": self.workers,
            "reload": self.reload,
            "log_level": self.log_level,
            "proxy_headers": self.proxy_headers,
            "forwarded_allow_ips": self.forwarded_allow_ips,
            "lifespan": self.lifespan,
        }


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
    fastapi: FastAPIConfig = field(default_factory=FastAPIConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


@dataclass
class DatabaseConfig:
    name: str = "default"
    type: str = "sqlite"
    url: str = "sqlite:///./xcore.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False
    database: str | None = None
    max_connections: int | None = None

    # ── Pool & fiabilité ──────────────────────────────────────
    pool_pre_ping: bool = True
    # Recycle la connexion avant que MySQL/MariaDB ne la coupe
    # Règle : pool_recycle < wait_timeout BDD (SHOW VARIABLES LIKE 'wait_timeout')
    pool_recycle: int = 1800
    # Timeout d'acquisition d'une connexion depuis le pool
    pool_timeout: int = 30
    # Que faire quand une connexion retourne au pool
    # "rollback" (défaut, sûr) | "commit" | "none" (perf max, risqué)
    pool_reset_on_return: str = "rollback"

    # ── Timeouts driver-level ─────────────────────────────────
    # Passés directement au driver (aiomysql, asyncpg, psycopg2…)
    # Exemple MySQL : {"connect_timeout": 10, "read_timeout": 30, "write_timeout": 30}
    # Exemple PostgreSQL asyncpg : {"command_timeout": 30, "timeout": 10}
    connect_args: dict = field(default_factory=dict)

    # ── Isolation & comportement transactionnel ───────────────
    # "READ COMMITTED" | "REPEATABLE READ" | "SERIALIZABLE" | "AUTOCOMMIT"
    isolation_level: str | None = None

    # ── Options d'exécution SQLAlchemy ────────────────────────
    # Ex: {"compiled_cache": None} pour désactiver le cache de requêtes
    execution_options: dict = field(default_factory=dict)


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
    url: str = "redis://localhost:6379/0"
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
class EphemeralConfig:
    """
    Configuration du warm pool pour les plugins Ephemeral.

    pool_size        → nombre d'instances pré-chargées en attente
    max_idle_seconds → durée avant qu'une instance idle soit déchargée
    max_concurrent   → instances simultanées max (cold boot au-delà)
    boot_timeout     → timeout de chargement d'une instance (secondes)

    Dans plugin.yaml :
        execution_mode: ephemeral
        ephemeral:
          pool_size: 3
          max_idle_seconds: 60
          max_concurrent: 10
          boot_timeout: 5
    """

    pool_size: int = 0  # 0 = pas de warm pool (cold boot pur)
    max_idle_seconds: int = 60
    max_concurrent: int = 10
    boot_timeout: float = 5.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EphemeralConfig":
        valid = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        return cls(**{k: v for k, v in d.items() if k in valid})

    @classmethod
    def default(cls) -> "EphemeralConfig":
        return cls()


@dataclass
class TenancyConfig:
    """
    Configuration du système multi-tenant.

    enabled          → active/désactive tout le système (défaut: False)
    header           → nom du header HTTP lu pour extraire le tenant_id
    subdomain        → active l'extraction depuis le sous-domaine
    default_tenant   → tenant utilisé si aucun header/sous-domaine trouvé
    isolate_cache      → préfixe automatique des clés cache par tenant_id
    isolate_db         → applique SET search_path par tenant_id (PostgreSQL)
    isolate_scheduler  → préfixe les job_id APScheduler par tenant_id
    enforce_ipc        → active la vérification allowed_callers sur IPC
    """

    enabled: bool = False
    header: str = "X-Tenant-ID"
    subdomain: bool = False
    default_tenant: str = "default"
    isolate_cache: bool = True
    isolate_db: bool = True
    isolate_scheduler: bool = False
    enforce_ipc: bool = True


@dataclass
class __TenancyConfig:
    """
    Configuration du système multi-tenant.

    enabled          → active/désactive tout le système (défaut: False)
    enforce_ipc        → active la vérification allowed_callers sur IPC
    """

    enabled: bool = False
    enforce_ipc: bool = True


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

    ephemeral: EphemeralConfig = field(default_factory=EphemeralConfig)
    tenancy: TenancyConfig = field(default_factory=TenancyConfig)


@dataclass
class LoggingConfig:
    level: str = "INFO"
    output: str = "text"  # "text" | "json"
    # ignoré si output=text|json
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
class CORSConfig:
    allow_origins: list = field(default_factory=list)
    allow_credentials: bool = False
    allow_methods: list[str] = field(default_factory=list)
    allow_headers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow_origins": self.allow_origins,
            "allow_credentials": self.allow_credentials,
            "allow_methods": self.allow_methods,
            "allow_headers": self.allow_headers,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CORSConfig":
        return cls(
            allow_origins=value.get("allow_origins", []),
            allow_credentials=value.get("allow_credentials", False),
            allow_methods=value.get("allow_methods", []),
            allow_headers=value.get("allow_headers", []),
        )


@dataclass
class MiddleParams:
    type: Literal["internal", "external", "events"] = (
        "external"  # add events bus systeme
    )
    name: str = ""
    value: Any = None


@dataclass
class MiddlewareConfig:
    name: str
    module: str | None = None
    config: list[MiddleParams] = field(default_factory=list)


@dataclass
class XcoreConfig:
    app: AppConfig = field(default_factory=AppConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    services: ServicesConfig = field(default_factory=ServicesConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    marketplace: MarketplaceConfig = field(default_factory=MarketplaceConfig)
    tenancy: TenancyConfig = field(default_factory=TenancyConfig)
    raw: dict[str, Any] = field(default_factory=dict)
    middleware: list[MiddlewareConfig] = field(default_factory=list)
    cors: CORSConfig = field(default_factory=CORSConfig)
