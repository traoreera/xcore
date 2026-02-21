"""
Configuration loader — lit integration.yaml et expose une config typée.

Fonctionnalités :
    - Chargement du .env via env_variable.env_file
    - Substitution ${VAR} dans tout le YAML après chargement du .env
    - Surcharge par variables d'environnement INTEGRATION__SECTION__KEY=value
    - Chaque ExtensionConfig expose un dict `env` avec ses variables résolues
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from .schemas import (
    AppConfig,
    CacheConfig,
    DatabaseConfig,
    ExtensionConfig,
    IntegrationConfig,
    LoggingConfig,
    SchedulerConfig,
    SchedulerJobConfig,
)

logger = logging.getLogger("integrations.config")

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


# ─────────────────────────────────────────────────────────────
# Chargement du .env
# ─────────────────────────────────────────────────────────────


def _load_dotenv(env_file: str) -> None:
    """
    Charge un fichier .env dans os.environ.
    Syntaxe supportée : KEY=value, KEY="value", # commentaires.
    Utilise python-dotenv si disponible, sinon parser minimal intégré.
    """
    path = Path(env_file)
    if not path.exists():
        logger.warning(f".env introuvable : {env_file}")
        return

    with contextlib.suppress(ImportError):
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(filename=path, raise_error_if_not_found=False))
        logger.info(f".env chargé via python-dotenv : {env_file}")
        return

    # Parser minimal sans dépendance
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:  # on ne surcharge pas l'env système
                os.environ[key] = value
    logger.info(f".env chargé (parser intégré) : {env_file}")


def _resolve_env(value: Any) -> Any:
    """Remplace ${VAR} par os.environ[VAR] dans toute la structure YAML."""
    if isinstance(value, str):

        def _replace(m):
            var = m.group(1)
            result = os.environ.get(var)
            if result is None:
                logger.warning(f"Variable d'environnement non définie : ${{{var}}}")
                return ""
            return result

        return _ENV_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    return [_resolve_env(v) for v in value] if isinstance(value, list) else value


# ─────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────
class ConfigLoader:
    """
    Charge integration.yaml et expose une IntegrationConfig typée.

    Ordre de résolution :
      1. Lecture du YAML brut
      2. Chargement du .env (si env_variable.inject: true)
      3. Substitution ${VAR} dans tout le YAML
      4. Surcharges INTEGRATION__SECTION__KEY depuis l'environnement
      5. Parsing en dataclasses

    Usage :
        cfg = ConfigLoader.load()
        cfg = ConfigLoader.load("config/integration.yaml")
    """

    DEFAULT_PATHS = [
        Path("integration.yaml"),
        Path("config/integration.yaml"),
        Path("integrations/integration.yaml"),
    ]

    @classmethod
    def load(cls, path: Optional[str | Path] = None) -> IntegrationConfig:
        raw = cls._read_yaml(path)
        cls._handle_dotenv(raw)  # 1. charge le .env si demandé
        raw = _resolve_env(raw)  # 2. substitution ${VAR}
        raw = cls._apply_env_overrides(raw)  # 3. INTEGRATION__KEY=value
        return cls._parse(raw)

    # ── YAML ──────────────────────────────────────────────────

    @classmethod
    def _read_yaml(cls, path: Optional[str | Path]) -> Dict[str, Any]:
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML non installé — pip install pyyaml")
            return {}

        candidates = [Path(path)] if path else cls.DEFAULT_PATHS
        for candidate in candidates:
            if candidate.exists():
                with open(candidate, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                logger.info(f"Configuration chargée depuis {candidate}")
                return data

        logger.warning("Aucun fichier integration.yaml trouvé — valeurs par défaut.")
        return {}

    # ── .env ──────────────────────────────────────────────────

    @classmethod
    def _handle_dotenv(cls, raw: Dict[str, Any]) -> None:
        """Charge le .env si env_variable.inject est true dans le YAML."""
        env_cfg = raw.get("env_variable", {})
        if not env_cfg.get("inject", False):
            return
        env_file = env_cfg.get("env_file", ".env")
        _load_dotenv(env_file)

    # ── ENV OVERRIDES ─────────────────────────────────────────

    @classmethod
    def _apply_env_overrides(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """INTEGRATION__APP__DEBUG=true surcharge app.debug dans le YAML."""
        prefix = "INTEGRATION__"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            parts = key[len(prefix) :].lower().split("__")
            target = raw
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            if value.lower() in ("true", "1", "yes"):
                value = True
            elif value.lower() in ("false", "0", "no"):
                value = False
            elif value.isdigit():
                value = int(value)
            target[parts[-1]] = value
        return raw

    # ── PARSERS ───────────────────────────────────────────────

    @classmethod
    def _parse(cls, raw: Dict[str, Any]) -> IntegrationConfig:
        return IntegrationConfig(
            app=cls._parse_app(raw.get("app", {})),
            extensions=cls._parse_extensions(raw.get("extensions", {})),
            databases=cls._parse_databases(raw.get("databases", {})),
            cache=cls._parse_cache(raw.get("cache", {})),
            scheduler=cls._parse_scheduler(raw.get("scheduler", {})),
            logging=cls._parse_logging(raw.get("logging", {})),
            raw=raw,
        )

    @staticmethod
    def _parse_app(d: Dict) -> AppConfig:
        return AppConfig(
            name=d.get("name", "App"),
            env=d.get("env", "development"),
            debug=d.get("debug", False),
        )

    @staticmethod
    def _parse_extensions(d: Dict) -> Dict[str, ExtensionConfig]:
        result = {}
        for name, cfg in d.items():
            if not isinstance(cfg, dict):
                continue
            # Le bloc `env` est déjà résolu par _resolve_env()
            # on le récupère tel quel — ce sont les valeurs finales
            env_vars = cfg.get("env", {})
            result[name] = ExtensionConfig(
                name=name,
                service=cfg.get("service", ""),
                enabled=cfg.get("enabled", True),
                background=cfg.get("background", False),
                background_mode=cfg.get("background_mode", "async"),
                background_restart=cfg.get("background_restart", True),
                background_jobs=cfg.get("background_jobs", []),
                config=cfg.get("config", {}),
                env=env_vars,
            )
        return result

    @staticmethod
    def _parse_databases(d: Dict) -> Dict[str, DatabaseConfig]:
        return {
            name: DatabaseConfig(
                name=name,
                type=cfg.get("type", "sqlite"),
                url=cfg.get("url", ""),
                pool_size=cfg.get("pool_size", 5),
                max_overflow=cfg.get("max_overflow", 10),
                echo=cfg.get("echo", False),
                database=cfg.get("database"),
                max_connections=cfg.get("max_connections"),
            )
            for name, cfg in d.items()
        }

    @staticmethod
    def _parse_cache(d: Dict) -> CacheConfig:
        return CacheConfig(
            backend=d.get("backend", "memory"),
            ttl=d.get("ttl", 300),
            max_size=d.get("max_size", 1000),
            url=d.get("url"),
        )

    @staticmethod
    def _parse_scheduler(d: Dict) -> SchedulerConfig:
        jobs = []
        for j in d.get("jobs", []):
            extra = {
                k: v
                for k, v in j.items()
                if k
                not in (
                    "id",
                    "func",
                    "trigger",
                    "enabled",
                    "seconds",
                    "minutes",
                    "hour",
                    "minute",
                    "day_of_week",
                    "grace_time",
                )
            }
            jobs.append(
                SchedulerJobConfig(
                    id=j["id"],
                    func=j["func"],
                    trigger=j.get("trigger", "interval"),
                    enabled=j.get("enabled", True),
                    seconds=j.get("seconds"),
                    minutes=j.get("minutes"),
                    hour=j.get("hour"),
                    minute=j.get("minute"),
                    day_of_week=j.get("day_of_week"),
                    extra=extra,
                )
            )
        return SchedulerConfig(
            enabled=d.get("enabled", True),
            backend=d.get("backend", "memory"),
            timezone=d.get("timezone", "UTC"),
            jobs=jobs,
        )

    @staticmethod
    def _parse_logging(d: Dict) -> LoggingConfig:
        return LoggingConfig(
            level=d.get("level", "INFO"),
            format=d.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
            handlers=d.get("handlers", {}),
        )


# ─────────────────────────────────────────────────────────────
# Singleton global
# ─────────────────────────────────────────────────────────────

_config: Optional[IntegrationConfig] = None


def get_config(path: Optional[str | Path] = None) -> IntegrationConfig:
    """Retourne la config globale (singleton)."""
    global _config
    if _config is None:
        _config = ConfigLoader.load(path)
    return _config


def reload_config(path: Optional[str | Path] = None) -> IntegrationConfig:
    """Force le rechargement de la configuration."""
    global _config
    _config = ConfigLoader.load(path)
    return _config
