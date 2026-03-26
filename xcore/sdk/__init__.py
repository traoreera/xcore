"""
sdk/ — Kit de développement pour les auteurs de plugins xcore.

Import recommandé dans un plugin :
    from xcore.sdk import TrustedBase, sandboxed, ok, error
    from xcore.sdk import PluginManifest
"""

from ..kernel.api.contract import BasePlugin, ExecutionMode, TrustedBase, error, ok
from ..kernel.api.rbac import RBACChecker, require_permission, require_role
from .adapter.asyncsql import BaseAsyncRepository
from .adapter.syncsql import BaseSyncRepository
from .routers import RouterRegistry
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
    "BaseAsyncRepository",
    "BaseSyncRepository",
    "RBACChecker",
    "require_permission",
    "require_role",
    "RouterRegistry",
]
