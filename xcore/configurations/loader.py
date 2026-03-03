"""
ConfigLoader v2 — load xcore.yaml with :
  - substitution ${ENV_VAR}
  - overloads XCORE__SECTION__KEY=value
  - default values in xcore.yaml
  - key secret_key automatically converted to bytes
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .helper import _resolve
from .sections import (
    AppConfig,
    CacheConfig,
    DatabaseConfig,
    LoggingConfig,
    MetricsConfig,
    ObservabilityConfig,
    PluginConfig,
    SchedulerConfig,
    SecurityConfig,
    ServicesConfig,
    TracingConfig,
    XcoreConfig,
)

logger = logging.getLogger("xcore.config")

# ─────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────


class ConfigLoader:
    """
    Charge xcore.yaml (ou xcore.json) et expose une XcoreConfig typée.

    Resolution process:
      1. Read YAML / JSON
      2. Injection .env (if app.dotenv is definied)
      3. Substitution ${VAR}
      4. Overloads de XCORE__SECTION__KEY from env
      5. Parsing dataclasses

    no config -> default config not secure.

    Use:
       ```python
        cfg = ConfigLoader.load()
        cfg = ConfigLoader.load("config/xcore.yaml")
        ```
    """

    DEFAULT_PATHS = [
        Path("integration.yaml"),
        Path("integration.yml"),
        Path("integration.json"),
        Path("config/integration.yaml"),
    ]

    @classmethod
    def load(cls, path: str | Path | None = None) -> XcoreConfig:
        raw = cls._read(path)
        cls._load_dotenv(raw)
        raw = _resolve(raw)
        raw = cls._apply_env_overrides(raw)
        return cls._parse(raw)

    # ── YAML / JSON ───────────────────────────────────────────

    @classmethod
    def _read(cls, path: str | Path | None) -> dict[str, Any]:
        candidates = [Path(path)] if path else cls.DEFAULT_PATHS

        for candidate in candidates:
            if not candidate.exists():
                continue
            suffix = candidate.suffix.lower()
            try:
                if suffix in (".yaml", ".yml"):
                    import yaml

                    with open(candidate, encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                else:
                    import json

                    with open(candidate, encoding="utf-8") as f:
                        data = json.load(f)
                logger.info(f"conf loaded : {candidate}")
                return data
            except ImportError:
                logger.warning("pyyaml no install — pip install pyyaml")
                return {}
            except Exception as e:
                logger.error(f"error reading file {candidate} : {e}")
                return {}

        logger.info("no conf file will not found. default config will be used.")
        return {}

    # ── .env ──────────────────────────────────────────────────

    @classmethod
    def _load_dotenv(cls, raw: dict[str, Any]) -> None:
        dotenv_file = raw.get("app", {}).get("dotenv")
        if not dotenv_file:
            return
        path = Path(dotenv_file)
        if not path.exists():
            logger.warning(f"dotenv introuvable : {path}")
            return
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=path, override=False)
            logger.info(f".env loaded : {path}")
        except ImportError:
            logger.warning("python-dotenv not installed — pip install python-dotenv")

    # ── Surcharges ENV ────────────────────────────────────────

    @classmethod
    def _apply_env_overrides(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """XCORE__APP__DEBUG=true surcharge app.debug."""
        prefix = "XCORE__"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            parts = key[len(prefix) :].lower().split("__")
            target = raw
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            # Corecition de type
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes"):
                    value = True
                elif value.lower() in ("false", "0", "no"):
                    value = False
                elif value.isdigit():
                    value = int(value)
            target[parts[-1]] = value
        return raw

    # ── Parsers ───────────────────────────────────────────────

    @classmethod
    def _parse(cls, raw: dict[str, Any]) -> XcoreConfig:
        return XcoreConfig(
            app=cls._parse_app(raw.get("app", {})),
            plugins=cls._parse_plugins(raw.get("plugins", {})),
            services=cls._parse_services(raw.get("services", {})),
            observability=cls._parse_observability(raw.get("observability", {})),
            security=cls._parse_security(raw.get("security", {})),
            raw=raw,
        )

    @staticmethod
    def _parse_app(d: dict) -> AppConfig:
        sk = d.get("secret_key", f"change-me-in-production")
        if isinstance(sk, str):
            sk = sk.encode()
        return AppConfig(
            name=d.get("name", "xcore-app"),
            env=d.get("env", "development"),
            debug=d.get("debug", False),
            secret_key=sk,
            plugin_prefix=d.get("plugin_prefix", "/plugin"),
            plugin_tags=d.get("plugin_tags", []),
        )

    @staticmethod
    def _parse_plugins(d: dict) -> PluginConfig:
        sk = d.get("secret_key", "change-me-in-production")
        if isinstance(sk, str):
            sk = sk.encode()
        return PluginConfig(
            directory=d.get("directory", "./plugins"),
            secret_key=sk,
            strict_trusted=d.get("strict_trusted", True),
            interval=d.get("interval", 2),
            entry_point=d.get("entry_point", "src/main.py"),
            snapshot=d.get(
                "snapshot",
                {
                    "extensions": [".log", ".pyc", ".html"],
                    "filenames": ["__pycache__", "__init__.py", ".env"],
                    "hidden": True,
                },
            ),
        )

    @classmethod
    def _parse_services(cls, d: dict) -> ServicesConfig:
        dbs: dict[str, DatabaseConfig] = {
            name: DatabaseConfig(
                name=name,
                type=cfg.get("type", "sqlite"),
                url=cfg.get("url", "sqlite:///./xcore.db"),
                pool_size=cfg.get("pool_size", 5),
                max_overflow=cfg.get("max_overflow", 10),
                echo=cfg.get("echo", False),
                database=cfg.get("database"),
                max_connections=cfg.get("max_connections"),
            )
            for name, cfg in d.get("databases", {}).items()
        }
        c = d.get("cache", {})
        cache = CacheConfig(
            backend=c.get("backend", "memory"),
            ttl=c.get("ttl", 300),
            max_size=c.get("max_size", 1000),
            url=c.get("url"),
        )

        s = d.get("scheduler", {})
        scheduler = SchedulerConfig(
            enabled=s.get("enabled", True),
            backend=s.get("backend", "memory"),
            timezone=s.get("timezone", "UTC"),
            jobs=s.get("jobs", []),
        )

        return ServicesConfig(
            databases=dbs,
            cache=cache,
            scheduler=scheduler,
            extensions=d.get("extensions", {}),
        )

    @staticmethod
    def _parse_observability(d: dict) -> ObservabilityConfig:
        lg = d.get("logging", {})
        mt = d.get("metrics", {})
        tr = d.get("tracing", {})
        return ObservabilityConfig(
            logging=LoggingConfig(
                level=lg.get("level", "INFO"),
                format=lg.get(
                    "format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                ),
                file=lg.get("file"),
                max_bytes=lg.get("max_bytes", 10_485_760),
                backup_count=lg.get("backup_count", 5),
            ),
            metrics=MetricsConfig(
                enabled=mt.get("enabled", False),
                backend=mt.get("backend", "memory"),
                prefix=mt.get("prefix", "xcore"),
            ),
            tracing=TracingConfig(
                enabled=tr.get("enabled", False),
                backend=tr.get("backend", "noop"),
                service_name=tr.get("service_name", "xcore"),
                endpoint=tr.get("endpoint"),
            ),
        )

    @staticmethod
    def _parse_security(d: dict) -> SecurityConfig:
        return SecurityConfig(
            allowed_imports=d.get("allowed_imports", []),
            forbidden_imports=d.get("forbidden_imports", []),
            rate_limit_default=d.get(
                "rate_limit_default", {"calls": 100, "period_seconds": 60}
            ),
        )


# ─────────────────────────────────────────────────────────────
# Singleton global
# ─────────────────────────────────────────────────────────────

_config: XcoreConfig | None = None


def get_config(path: str | Path | None = None) -> XcoreConfig:
    global _config
    if _config is None:
        _config = ConfigLoader.load(path)
    return _config


def reload_config(path: str | Path | None = None) -> XcoreConfig:
    global _config
    return ConfigLoader.load(path)
