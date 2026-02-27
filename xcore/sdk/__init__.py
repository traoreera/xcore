"""
sdk/ — Kit de développement pour les auteurs de plugins xcore.

Import recommandé dans un plugin :
    from xcore.sdk import TrustedBase, sandboxed, ok, error
    from xcore.sdk import PluginManifest
"""

from ..kernel.api.contract import BasePlugin, ExecutionMode, TrustedBase, error, ok
from .decorators import (
    AutoDispatchMixin,
    RoutedPlugin,
    action,
    require_service,
    route,
    sandboxed,
    trusted,
    validate_payload,
)
from .plugin_base import PluginManifest, ResourceConfig, RuntimeConfig

__all__ = [
    "TrustedBase",
    "BasePlugin",
    "ok",
    "error",
    "ExecutionMode",
    "PluginManifest",
    "ResourceConfig",
    "RuntimeConfig",
    "action",
    "sandboxed",
    "trusted",
    "require_service",
    "validate_payload",
    "route",
    "RoutedPlugin",
    "AutoDispatchMixin",
]
