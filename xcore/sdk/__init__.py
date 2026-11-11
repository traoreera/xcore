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

import importlib
import importlib.util
from typing import TYPE_CHECKING

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

# ── Ce qui ne s'importe qu'à la demande (PEP 562) ──────────────────────────
#
# Trois familles de noms que ce namespace expose SANS les importer à l'import :
#
# - les adaptateurs SQL : SQLAlchemy est optionnel depuis la 2.7.0
#   (XCoreRuntime[db], [postgres], [sqlite]) et les importer faisait planter
#   `import xcore` — donc le boot — sur un simple `pip install XCoreRuntime` ;
# - le service de tâches (`WorkerService`, `task`, `task_registry`) : il tire
#   CELERY, mesuré à ~52 ms d'import, payés par toute application qui fait
#   `import xcore` et par CHAQUE worker sandbox à chaque recyclage, même sans
#   service de tâches configuré (#305, #306) ;
# - les fonctionnalités du package externe `xcoresdk`, qui tire SQLAlchemy par
#   son module d'authentification : ~102 ms de plus, dans les mêmes conditions.
#
# Soit ~154 ms sur les ~594 ms d'`import xcore`, et autant par worker sandbox.
# L'accès reste identique pour l'appelant (`from xcore.sdk import WorkerService`) :
# c'est le PREMIER accès qui paie l'import, et lui seul.
_SQL_ADAPTERS = {
    "BaseAsyncRepository": ".adapter.asyncsql",
    "BaseSyncRepository": ".adapter.syncsql",
}
_WORKER = dict.fromkeys(
    ("WorkerService", "task", "task_registry"), "..services.xworker"
)
# Pas d'équivalent local : absentes plutôt que simulées (un faux `@cached` qui ne
# cache rien silencieusement serait pire qu'une ImportError explicite).
_XCORESDK = dict.fromkeys(
    (
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
    ),
    "sdk",
)
_LAZY = {**_SQL_ADAPTERS, **_WORKER, **_XCORESDK}

if TYPE_CHECKING:  # pragma: no cover
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

    from ..services.xworker import WorkerService, task, task_registry
    from .adapter.asyncsql import BaseAsyncRepository
    from .adapter.syncsql import BaseSyncRepository

# `find_spec` RÉSOUT sans exécuter (mesuré : 0,05 ms) : `from xcore.sdk import *` ne doit
# pas lever pour une dépendance que l'utilisateur n'a pas, et ne doit pas non plus importer
# celery ou SQLAlchemy juste pour savoir s'ils sont là.
__all__ += list(_WORKER)
if importlib.util.find_spec("sqlalchemy") is not None:
    __all__ += list(_SQL_ADAPTERS)
if importlib.util.find_spec("sdk") is not None:
    __all__ += list(_XCORESDK)
else:
    get_logger("xcore.sdk").debug(
        "package xcoresdk non installé — EventMixin/HookMixin/ObservabilityMixin/"
        "ScheduledMixin/cached/invalidate/cron/interval/health_check/AutoMixin/"
        "BaseMongoRepository/BaseRedisRepository indisponibles dans xcore.sdk"
    )

#: Ce qu'il faut installer pour le nom manquant, quand l'import échoue.
_MISSING = {
    "sqlalchemy": "pip install 'XCoreRuntime[db]'",
    "celery": "pip install 'XCoreRuntime[worker]'",
    "sdk": "le package externe xcoresdk",
}


def __getattr__(name: str):
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = importlib.import_module(
            module_name, __name__ if module_name[0] == "." else None
        )
    except ModuleNotFoundError as e:
        missing = (e.name or "").split(".")[0]
        if missing in _MISSING:
            raise ImportError(
                f"xcore.sdk.{name} demande {missing}, une dépendance optionnelle — {_MISSING[missing]}"
            ) from e
        raise
    value = getattr(module, name)
    globals()[
        name
    ] = value  # mis en cache : __getattr__ n'est appelé qu'une fois par nom
    return value
