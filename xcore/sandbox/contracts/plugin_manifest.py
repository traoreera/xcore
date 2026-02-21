"""
contracts/plugin_manifest.py
─────────────────────────────
Parsing complet du manifeste plugin.yaml.
Les valeurs par défaut dépendent du mode d'exécution (Trusted vs Sandboxed).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ══════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════


class ExecutionMode(str, Enum):
    TRUSTED = "trusted"
    SANDBOXED = "sandboxed"
    LEGACY = "legacy"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ══════════════════════════════════════════════
# Defaults par mode
# ══════════════════════════════════════════════

_TRUSTED_DEFAULTS = {
    "resources": {
        "timeout_seconds": 30,
        "max_memory_mb": 0,  # illimité
        "max_disk_mb": 0,  # illimité
        "rate_limit": {
            "calls": 1000,
            "period_seconds": 60,
        },
    },
    "runtime": {
        "log_level": "INFO",
        "health_check": {
            "enabled": False,  # pas de subprocess à surveiller
            "interval_seconds": 60,
            "timeout_seconds": 5,
        },
        "retry": {
            "max_attempts": 1,  # crash trusted = crash contrôlé, pas de retry
            "backoff_seconds": 0.0,
        },
    },
    "filesystem": {
        "allowed_paths": ["*"],  # accès complet
        "denied_paths": [],
    },
}

_SANDBOXED_DEFAULTS = {
    "resources": {
        "timeout_seconds": 10,
        "max_memory_mb": 128,
        "max_disk_mb": 50,
        "rate_limit": {
            "calls": 100,
            "period_seconds": 60,
        },
    },
    "runtime": {
        "log_level": "INFO",
        "health_check": {
            "enabled": True,
            "interval_seconds": 30,
            "timeout_seconds": 3,
        },
        "retry": {
            "max_attempts": 3,
            "backoff_seconds": 0.5,
        },
    },
    "filesystem": {
        "allowed_paths": ["data/"],
        "denied_paths": ["src/"],
    },
}


def _defaults_for(mode: ExecutionMode) -> dict:
    """Retourne les defaults selon le mode."""
    if mode in (ExecutionMode.TRUSTED, ExecutionMode.LEGACY):
        return _TRUSTED_DEFAULTS
    return _SANDBOXED_DEFAULTS


# ══════════════════════════════════════════════
# Sous-sections
# ══════════════════════════════════════════════


@dataclass
class RateLimitConfig:
    calls: int = 100
    period_seconds: float = 60.0

    @classmethod
    def from_dict(cls, d: dict, defaults: dict) -> "RateLimitConfig":
        return cls(
            calls=int(d.get("calls", defaults["calls"])),
            period_seconds=float(d.get("period_seconds", defaults["period_seconds"])),
        )


@dataclass
class ResourceConfig:
    timeout_seconds: float = 10.0
    max_memory_mb: int = 128
    max_disk_mb: int = 50
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    @classmethod
    def from_dict(cls, d: dict, defaults: dict) -> "ResourceConfig":
        return cls(
            timeout_seconds=float(
                d.get("timeout_seconds", defaults["timeout_seconds"])
            ),
            max_memory_mb=int(d.get("max_memory_mb", defaults["max_memory_mb"])),
            max_disk_mb=int(d.get("max_disk_mb", defaults["max_disk_mb"])),
            rate_limit=RateLimitConfig.from_dict(
                d.get("rate_limit", {}),
                defaults["rate_limit"],
            ),
        )


@dataclass
class HealthCheckConfig:
    enabled: bool = True
    interval_seconds: float = 30.0
    timeout_seconds: float = 3.0

    @classmethod
    def from_dict(cls, d: dict, defaults: dict) -> "HealthCheckConfig":
        return cls(
            enabled=bool(d.get("enabled", defaults["enabled"])),
            interval_seconds=float(
                d.get("interval_seconds", defaults["interval_seconds"])
            ),
            timeout_seconds=float(
                d.get("timeout_seconds", defaults["timeout_seconds"])
            ),
        )


@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_seconds: float = 0.5

    @classmethod
    def from_dict(cls, d: dict, defaults: dict) -> "RetryConfig":
        return cls(
            max_attempts=int(d.get("max_attempts", defaults["max_attempts"])),
            backoff_seconds=float(
                d.get("backoff_seconds", defaults["backoff_seconds"])
            ),
        )


@dataclass
class RuntimeConfig:
    log_level: LogLevel = LogLevel.INFO
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)

    @classmethod
    def from_dict(cls, d: dict, defaults: dict) -> "RuntimeConfig":
        raw_level = d.get("log_level", defaults.get("log_level", "INFO")).upper()
        try:
            level = LogLevel(raw_level)
        except ValueError:
            level = LogLevel.INFO
        return cls(
            log_level=level,
            health_check=HealthCheckConfig.from_dict(
                d.get("health_check", {}), defaults["health_check"]
            ),
            retry=RetryConfig.from_dict(d.get("retry", {}), defaults["retry"]),
        )


@dataclass
class FilesystemConfig:
    allowed_paths: list[str] = field(default_factory=lambda: ["data/"])
    denied_paths: list[str] = field(default_factory=lambda: ["src/"])

    @classmethod
    def from_dict(cls, d: dict, defaults: dict) -> "FilesystemConfig":
        return cls(
            allowed_paths=d.get("allowed_paths", defaults["allowed_paths"]),
            denied_paths=d.get("denied_paths", defaults["denied_paths"]),
        )


# ══════════════════════════════════════════════
# Manifeste complet
# ══════════════════════════════════════════════


@dataclass
class PluginManifest:
    # ── Identité ──────────────────────────────
    name: str
    version: str
    execution_mode: ExecutionMode
    author: str = "unknown"
    description: str = ""
    framework_version: str = ">=1.0"
    entry_point: str = "src/main.py"
    allowed_imports: list[str] = field(default_factory=list)

    # ── Config prod (defaults selon mode) ─────
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    env: dict[str, str] = field(default_factory=dict)
    filesystem: FilesystemConfig = field(default_factory=FilesystemConfig)

    # ── Divers ────────────────────────────────
    extra: dict[str, Any] = field(default_factory=dict)
    plugin_dir: Path = field(default_factory=Path, repr=False)

    requires: list[str] = field(default_factory=list)

    def is_trusted(self) -> bool:
        return self.execution_mode in (ExecutionMode.TRUSTED, ExecutionMode.LEGACY)

    def is_sandboxed(self) -> bool:
        return self.execution_mode == ExecutionMode.SANDBOXED

    def effective_defaults(self) -> dict:
        """Retourne les defaults actifs pour ce manifeste."""
        return _defaults_for(self.execution_mode)


# ══════════════════════════════════════════════
# Erreurs
# ══════════════════════════════════════════════


class ManifestError(Exception):
    pass


# ══════════════════════════════════════════════
# Résolution des variables d'environnement
# ══════════════════════════════════════════════

_ENV_VAR_RE = re.compile(r"^\$\{(.+)\}$")


def _resolve_env(value: str) -> str:
    match = _ENV_VAR_RE.match(str(value))
    if not match:
        return str(value)
    var_name = match.group(1)
    resolved = os.environ.get(var_name)
    if resolved is None:
        raise ManifestError(
            f"Variable d'environnement '{var_name}' référencée dans plugin.yaml "
            "mais absente de l'environnement système."
        )
    return resolved


def _resolve_env_dict(raw: dict) -> dict[str, str]:
    return {k: _resolve_env(v) for k, v in raw.items()}


# ══════════════════════════════════════════════
# Chargement
# ══════════════════════════════════════════════


def _load_raw(plugin_dir: Path) -> dict[str, Any]:
    yaml_path = plugin_dir / "plugin.yaml"
    json_path = plugin_dir / "plugin.json"

    if yaml_path.exists():
        try:
            import yaml

            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except ImportError as e:
            raise ManifestError(
                "plugin.yaml trouvé mais pyyaml non installé. pip install pyyaml"
            ) from e
        except Exception as e:
            raise ManifestError(f"Impossible de lire plugin.yaml : {e}") from e

    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise ManifestError(f"Impossible de lire plugin.json : {e}") from e

    raise ManifestError(
        f"Aucun manifeste trouvé dans {plugin_dir} (plugin.yaml ou plugin.json requis)"
    )


def _inject_envfile(raw: dict, plugin_dir: Path):
    envfile_path = plugin_dir / raw.get("envfile", ".env")
    # import dotenv
    if raw.get("inject", False):
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(
            dotenv_path=find_dotenv(
                filename=envfile_path, raise_error_if_not_found=False
            )
        )


def load_manifest(plugin_dir: Path) -> PluginManifest:
    """
    Charge, valide et retourne le PluginManifest complet.
    Les defaults sont automatiquement ajustés selon execution_mode.
    """
    plugin_dir = Path(plugin_dir).resolve()
    raw = _load_raw(plugin_dir)

    # Champs obligatoires
    if missing := [f for f in ("name", "version") if not raw.get(f)]:
        raise ManifestError(f"Champs obligatoires manquants : {missing}")

    # Mode d'exécution
    raw_mode = raw.get("execution_mode", "legacy").lower()
    try:
        mode = ExecutionMode(raw_mode)
    except ValueError as e:
        raise ManifestError(
            f"execution_mode invalide : {raw_mode!r}. "
            f"Valeurs acceptées : {[m.value for m in ExecutionMode]}"
        ) from e

    # Defaults selon le mode — appliqués AVANT de lire le YAML
    # → le YAML surcharge uniquement les valeurs explicitement déclarées
    defaults = _defaults_for(mode)

    # Résolution des variables d'environnement
    try:
        _inject_envfile(raw.get("envconfiguration", {}), plugin_dir)
        resolved_env = _resolve_env_dict(raw.get("env", {}))
    except ManifestError:
        raise

    known_keys = {
        "name",
        "version",
        "execution_mode",
        "author",
        "description",
        "framework_version",
        "entry_point",
        "allowed_imports",
        "resources",
        "runtime",
        "env",
        "filesystem",
        "requires",  # ★ FIX : déclaré ici pour ne pas tomber dans extra{}
    }

    # ★ FIX : lecture du champ requires depuis le YAML
    # Avant : requires n'était jamais lu → tombait dans extra{} → toujours []
    # → _topo_sort voyait 0 dépendances → tous les plugins dans la même vague
    # → erp_auth démarrait EN MÊME TEMPS qu'erp_core → services["core"] absent
    raw_requires = raw.get("requires", []) or []
    if not isinstance(raw_requires, list):
        raise ManifestError(
            f"'requires' doit être une liste de noms de plugins, "
            f"reçu : {type(raw_requires).__name__}"
        )

    return PluginManifest(
        name=str(raw["name"]),
        version=str(raw["version"]),
        execution_mode=mode,
        author=raw.get("author", "unknown"),
        description=raw.get("description", ""),
        framework_version=raw.get("framework_version", ">=1.0"),
        entry_point=raw.get("entry_point", "src/main.py"),
        allowed_imports=raw.get("allowed_imports", []),
        resources=ResourceConfig.from_dict(
            raw.get("resources", {}), defaults["resources"]
        ),
        runtime=RuntimeConfig.from_dict(raw.get("runtime", {}), defaults["runtime"]),
        env=resolved_env,
        filesystem=FilesystemConfig.from_dict(
            raw.get("filesystem", {}), defaults["filesystem"]
        ),
        requires=raw_requires,  # ★ FIX : maintenant transmis au dataclass
        extra={k: v for k, v in raw.items() if k not in known_keys},
        plugin_dir=plugin_dir,
    )


# ══════════════════════════════════════════════
# Compatibilité framework
# ══════════════════════════════════════════════

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")


def _parse_version(v: str) -> tuple[int, ...]:
    m = _VERSION_RE.match(v.strip())
    if not m:
        raise ManifestError(f"Version invalide : {v!r}")
    return tuple(int(x) for x in m.groups() if x is not None)


def check_framework_compatibility(manifest: PluginManifest, core_version: str) -> bool:
    core = _parse_version(core_version)
    for part in manifest.framework_version.split(","):
        part = part.strip()
        for op in (">=", "<=", ">", "<", "=="):
            if part.startswith(op):
                target = _parse_version(part[len(op) :])
                ok = {
                    ">=": core >= target,
                    "<=": core <= target,
                    ">": core > target,
                    "<": core < target,
                    "==": core == target,
                }[op]
                if not ok:
                    return False
                break
    return True
