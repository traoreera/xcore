from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AppConfig:
    name: str = "App"
    env: str = "development"
    debug: bool = False


@dataclass
class ExtensionConfig:
    """
    Configuration d'une extension de service.

    Champs injectés automatiquement par le framework :
      - config : bloc `config` du YAML (variables déjà résolues)
      - env    : variables déclarées dans `env:` du bloc extension (résolues)

    Dans le service, accès via :
        self.config["host"]
        self.env["APP_TOKEN"]
    """

    name: str
    service: str  # "module.path:ClassName"
    enabled: bool = True
    background: bool = False
    background_mode: str = "async"  # async | thread | both
    background_restart: bool = True
    background_jobs: List[Dict] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    # ← variables d'env résolues
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class DatabaseConfig:
    name: str
    type: str = "sqlite"
    url: str = "sqlite:///./app.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False
    database: Optional[str] = None  # MongoDB
    max_connections: Optional[int] = None  # Redis


@dataclass
class CacheConfig:
    backend: str = "memory"  # memory | redis
    ttl: int = 300
    max_size: int = 1000
    url: Optional[str] = None


@dataclass
class SchedulerJobConfig:
    id: str
    func: str
    trigger: str = "interval"
    enabled: bool = True
    seconds: Optional[int] = None
    minutes: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    day_of_week: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    grace_time: Optional[int] = None


@dataclass
class SchedulerConfig:
    enabled: bool = True
    backend: str = "memory"  # memory | redis | database
    timezone: str = "UTC"
    jobs: List[SchedulerJobConfig] = field(default_factory=list)


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationConfig:
    app: AppConfig = field(default_factory=AppConfig)
    extensions: Dict[str, ExtensionConfig] = field(default_factory=dict)
    databases: Dict[str, DatabaseConfig] = field(default_factory=dict)
    cache: CacheConfig = field(default_factory=CacheConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    raw: Dict[str, Any] = field(default_factory=dict)
