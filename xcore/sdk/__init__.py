"""
xcore/sdk — Kit de développement pour les auteurs de plugins xcore.

Historique : ce SDK a été extrait dans le package externe `xcoresdk`
(https://github.com/xcore-team/xcoreSDK) pour alléger le runtime, puis
vendoré à nouveau ici le temps que `xcoresdk`/`xcoreCli` soient publiés
sur PyPI (PyPI refuse les packages avec une dépendance git directe dans
leurs métadonnées — voir pyproject.toml).

Le socle (manifest, décorateurs de base, adaptateurs SQL) est fourni
localement par ce module. Les fonctionnalités plus récentes de
`xcoresdk` qui n'ont pas d'équivalent local (EventMixin, HookMixin,
ObservabilityMixin, ScheduledMixin, cached/invalidate, cron/interval,
health_check comme décorateur, AutoMixin, BaseMongoRepository,
BaseRedisRepository) restent disponibles uniquement si `xcoresdk` est
installé séparément — sinon elles sont simplement absentes de ce
namespace plutôt que de faire planter l'import.

Import recommandé dans un plugin :
    from xcore.sdk import TrustedBase, action, ok, error
    from xcore.sdk import PluginManifest
"""

from ..kernel.api import (
    AuthBackend,
    AuthPayload,
    get_auth_backend,
    has_auth_backend,
    register_auth_backend,
    unregister_auth_backend,
)
from ..kernel.api.contract import BasePlugin, ExecutionMode, TrustedBase, error, ok
from ..kernel.api.rbac import RBACChecker, require_permission, require_role
from ..kernel.events import Event, HookResult
from ..kernel.observability import get_logger
from ..kernel.permissions.engine import PermissionDenied
from ..kernel.runtime.state_machine import PluginState
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
from .plugin_base import (
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
from .routers import RouterRegistry

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
    "PluginDependency",
    "ResourceConfig",
    "RuntimeConfig",
    "RateLimitConfig",
    "HealthCheckConfig",
    "RetryConfig",
    "FilesystemConfig",
    "VersionConstraint",
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
    # Events & Hooks
    "Event",
    "HookResult",
    # Observability
    "get_logger",
    # Worker (xcore services)
    "WorkerService",
    "task",
    "task_registry",
]

# ── Fonctionnalités xcoresdk sans équivalent local ─────────────────────────
# N'existent que si le package externe `xcoresdk` est installé en plus.
# Absentes ici plutôt que simulées : un faux no-op serait pire qu'une
# ImportError explicite (ex: un @cached qui ne cache rien silencieusement).
try:
    from sdk import (  # type: ignore[import-not-found]
        AutoMixin,
        BaseMongoRepository,
        BaseRedisRepository,
        EventMixin,
        HookMixin,
        ObservabilityMixin,
        ScheduledMixin,
        cached,
        counted,
        cron,
        health_check,
        interval,
        invalidate,
        on_event,
        on_hook,
        timed,
        traced,
    )

    __all__ += [
        "AutoMixin",
        "BaseMongoRepository",
        "BaseRedisRepository",
        "EventMixin",
        "HookMixin",
        "ObservabilityMixin",
        "ScheduledMixin",
        "cached",
        "counted",
        "cron",
        "health_check",
        "interval",
        "invalidate",
        "on_event",
        "on_hook",
        "timed",
        "traced",
    ]
except ImportError:
    get_logger("xcore.sdk").debug(
        "package xcoresdk non installé — EventMixin/HookMixin/ObservabilityMixin/"
        "ScheduledMixin/cached/invalidate/cron/interval/health_check/AutoMixin/"
        "BaseMongoRepository/BaseRedisRepository indisponibles dans xcore.sdk"
    )
