"""
sdk/ — Kit de développement pour les auteurs de plugins xcore.

Import recommandé dans un plugin :
    from xcore.sdk import TrustedBase, sandboxed, ok, error
    from xcore.sdk import PluginManifest
"""

from ..kernel.api.auth import (
    get_auth_backend,
    register_auth_backend,
    unregister_auth_backend,
)
from ..kernel.api.contract import BasePlugin, ExecutionMode, TrustedBase, error, ok
from ..kernel.api.rbac import (
    RBACChecker,
    get_current_user,
    require_permission,
    require_role,
)
from ..services.xworker import WorkerService, task, task_registry
from .adapter.asyncsql import BaseAsyncRepository
from .adapter.syncsql import BaseSyncRepository
from .decorators import (
    RoutedPlugin,
    action,
    require_service,
    route,
    sandboxed,
    schema,
    trusted,
    validate_payload,
)
from .mixin.ipc import AutoDispatchMixin
from .plugin_base import PluginManifest, ResourceConfig, RuntimeConfig
from .routers import RouterRegistry

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
    "WorkerService",
    "task_registry",
    "task",
    "register_auth_backend",
    "unregister_auth_backend",
    "get_auth_backend",
    "RouterRegistry",
    "get_current_user",
    "scheamas",
    "schema",
]
