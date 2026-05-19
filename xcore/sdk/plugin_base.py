"""Compatibility shim — re-exports from sdk.plugin_base (xcoresdk)."""

from sdk.plugin_base import (
    FilesystemConfig,
    HealthCheckConfig,
    PluginDependency,
    PluginManifest,
    RateLimitConfig,
    ResourceConfig,
    RetryConfig,
    RuntimeConfig,
    VersionConstraint,
)

__all__ = [
    "FilesystemConfig",
    "HealthCheckConfig",
    "PluginDependency",
    "PluginManifest",
    "RateLimitConfig",
    "ResourceConfig",
    "RetryConfig",
    "RuntimeConfig",
    "VersionConstraint",
]
