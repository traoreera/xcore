"""
xcore/sdk — Compatibility shim.

All SDK functionality now lives in the xcoresdk package:
    https://github.com/xcore-team/xcoreSDK

Plugin authors can import directly from xcoresdk:
    from sdk import TrustedBase, action, ok, error

Or continue using the xcore.sdk namespace (backward-compatible):
    from xcore.sdk import TrustedBase, action, ok, error
"""

from sdk import (
    AuthBackend,
    AuthPayload,
    AutoDispatchMixin,
    AutoMixin,
    BaseAsyncRepository,
    BaseMongoRepository,
    BasePlugin,
    BaseRedisRepository,
    BaseSyncRepository,
    Event,
    EventMixin,
    ExecutionMode,
    HookMixin,
    HookResult,
    ObservabilityMixin,
    PermissionDenied,
    PluginManifest,
    PluginState,
    RBACChecker,
    ResourceConfig,
    RoutedPlugin,
    RouterRegistry,
    RuntimeConfig,
    ScheduledMixin,
    TrustedBase,
    action,
    cached,
    counted,
    cron,
    error,
    get_auth_backend,
    get_logger,
    has_auth_backend,
    health_check,
    interval,
    invalidate,
    ok,
    on_event,
    on_hook,
    register_auth_backend,
    require_permission,
    require_role,
    require_service,
    route,
    sandboxed,
    timed,
    traced,
    trusted,
    unregister_auth_backend,
    validate_payload,
)
from sdk.decorators import schema

from ..services.xworker import WorkerService, task, task_registry

__all__ = [
    # Kernel contracts
    "TrustedBase",
    "BasePlugin",
    "ok",
    "error",
    "ExecutionMode",
    "PermissionDenied",
    "PluginState",
    # Manifest
    "PluginManifest",
    "ResourceConfig",
    "RuntimeConfig",
    # Core decorators
    "action",
    "schema",
    "sandboxed",
    "trusted",
    "require_service",
    "validate_payload",
    "route",
    "RoutedPlugin",
    "AutoDispatchMixin",
    "AutoMixin",
    "RouterRegistry",
    # RBAC
    "RBACChecker",
    "require_permission",
    "require_role",
    # Auth
    "AuthBackend",
    "AuthPayload",
    "register_auth_backend",
    "unregister_auth_backend",
    "get_auth_backend",
    "has_auth_backend",
    # DB adapters
    "BaseAsyncRepository",
    "BaseSyncRepository",
    "BaseMongoRepository",
    "BaseRedisRepository",
    # Events & Hooks
    "on_event",
    "on_hook",
    "EventMixin",
    "HookMixin",
    "Event",
    "HookResult",
    # Observability
    "get_logger",
    "traced",
    "counted",
    "timed",
    "health_check",
    "ObservabilityMixin",
    # Scheduler
    "cron",
    "interval",
    "ScheduledMixin",
    # Cache
    "cached",
    "invalidate",
    # Worker (xcore services)
    "WorkerService",
    "task",
    "task_registry",
]
