"""
plugin_base.py — Dataclasses du manifeste plugin v2.

PluginManifest est l'objet riche parsé par ManifestValidator.
Il remplace le _SimpleManifest pour les usages SDK complets.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..kernel.api.contract import ExecutionMode


@dataclass
class RateLimitConfig:
    calls: int = 100
    period_seconds: int = 60


@dataclass
class ResourceConfig:
    timeout_seconds: int = 10
    max_memory_mb: int = 128
    max_disk_mb: int = 50
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


@dataclass
class HealthCheckConfig:
    enabled: bool = True
    interval_seconds: int = 30
    timeout_seconds: int = 3


@dataclass
class RetryConfig:
    max_attempts: int = 1
    backoff_seconds: float = 0.0


@dataclass
class RuntimeConfig:
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)


@dataclass
class FilesystemConfig:
    allowed_paths: list[str] = field(default_factory=lambda: ["data/"])
    denied_paths:  list[str] = field(default_factory=lambda: ["src/"])


@dataclass
class PluginManifest:
    """
    Représentation complète et typée d'un manifeste plugin.yaml.

    Champs obligatoires : name, version
    Tous les autres ont des valeurs par défaut.
    """
    name: str
    version: str
    plugin_dir: Path

    # Identité
    author: str = "unknown"
    description: str = ""
    framework_version: str = ">=2.0"
    entry_point: str = "src/main.py"
    execution_mode: ExecutionMode = ExecutionMode.LEGACY

    # Dépendances et imports
    requires: list[str] = field(default_factory=list)
    allowed_imports: list[str] = field(default_factory=list)
    permissions: list[dict] = field(default_factory=list)

    # Environnement
    env: dict[str, str] = field(default_factory=dict)

    # Ressources, runtime, filesystem
    resources:   ResourceConfig   = field(default_factory=ResourceConfig)
    runtime:     RuntimeConfig    = field(default_factory=RuntimeConfig)
    filesystem:  FilesystemConfig = field(default_factory=FilesystemConfig)

    # Config arbitraire du plugin (bloc extra)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(
        cls,
        raw: dict[str, Any],
        mode: ExecutionMode,
        resolved_env: dict[str, str],
        requires: list[str],
        plugin_dir: Path,
    ) -> "PluginManifest":
        res_raw  = raw.get("resources", {})
        rt_raw   = raw.get("runtime", {})
        fs_raw   = raw.get("filesystem", {})
        rl_raw   = res_raw.get("rate_limit", {})
        hc_raw   = rt_raw.get("health_check", {})
        ret_raw  = rt_raw.get("retry", {})

        known = {
            "name", "version", "author", "description", "framework_version",
            "entry_point", "execution_mode", "requires", "allowed_imports",
            "permissions", "env", "envconfiguration",
            "resources", "runtime", "filesystem",
        }
        extra = {k: v for k, v in raw.items() if k not in known}

        return cls(
            name=str(raw["name"]),
            version=str(raw["version"]),
            plugin_dir=plugin_dir,
            author=raw.get("author", "unknown"),
            description=raw.get("description", ""),
            framework_version=raw.get("framework_version", ">=2.0"),
            entry_point=raw.get("entry_point", "src/main.py"),
            execution_mode=mode,
            requires=requires,
            allowed_imports=raw.get("allowed_imports", []),
            permissions=raw.get("permissions", []),
            env=resolved_env,
            resources=ResourceConfig(
                timeout_seconds=res_raw.get("timeout_seconds", 10),
                max_memory_mb=res_raw.get("max_memory_mb", 128),
                max_disk_mb=res_raw.get("max_disk_mb", 50),
                rate_limit=RateLimitConfig(
                    calls=rl_raw.get("calls", 100),
                    period_seconds=rl_raw.get("period_seconds", 60),
                ),
            ),
            runtime=RuntimeConfig(
                health_check=HealthCheckConfig(
                    enabled=hc_raw.get("enabled", True),
                    interval_seconds=hc_raw.get("interval_seconds", 30),
                    timeout_seconds=hc_raw.get("timeout_seconds", 3),
                ),
                retry=RetryConfig(
                    max_attempts=ret_raw.get("max_attempts", 1),
                    backoff_seconds=ret_raw.get("backoff_seconds", 0.0),
                ),
            ),
            filesystem=FilesystemConfig(
                allowed_paths=fs_raw.get("allowed_paths", ["data/"]),
                denied_paths=fs_raw.get("denied_paths", ["src/"]),
            ),
            extra=extra,
        )

    def __repr__(self) -> str:
        return (
            f"<PluginManifest name='{self.name}' version='{self.version}' "
            f"mode={self.execution_mode.value}>"
        )
