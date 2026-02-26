"""
sdk/ — Kit de développement pour les auteurs de plugins xcore.

Import recommandé dans un plugin :
    from xcore.sdk import TrustedBase, sandboxed, ok, error
    from xcore.sdk import PluginManifest
"""
from .plugin_base import PluginManifest, ResourceConfig, RuntimeConfig
from ..kernel.api.contract import TrustedBase, BasePlugin, ok, error, ExecutionMode
from .decorators import action, sandboxed, trusted, require_service, validate_payload, route, RoutedPlugin,AutoDispatchMixin

__all__ = [
    "TrustedBase", "BasePlugin", "ok", "error", "ExecutionMode",
    "PluginManifest", "ResourceConfig", "RuntimeConfig",
    "action", "sandboxed", "trusted", "require_service", "validate_payload",
    "route", "RoutedPlugin","AutoDispatchMixin"
]
