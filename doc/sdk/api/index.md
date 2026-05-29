---
title: SDK API Reference
description: All 49 public symbols exported by xcore.sdk, organized by category.
icon: material/api
---

# API Reference

xcoreSDK exposes **49 public symbols** from a single import path: `xcore.sdk`.

```python
from xcore.sdk import AutoMixin, action, ok, cached, traced, on_event, ...
```

---

## By category

| Category | Key exports |
|----------|-------------|
| [AutoMixin](automixin.md) | `AutoMixin` |
| [Decorators](decorators.md) | `action`, `route`, `schema`, `validate_payload`, `require_service`, `trusted`, `sandboxed` |
| [DB Adapters](adapters.md) | `BaseAsyncRepository`, `BaseSyncRepository`, `BaseMongoRepository`, `BaseRedisRepository` |
| [Events & Hooks](events.md) | `on_event`, `on_hook`, `EventMixin`, `HookMixin`, `Event`, `HookResult` |
| [Observability](observability.md) | `traced`, `counted`, `timed`, `health_check`, `ObservabilityMixin`, `get_logger` |
| [Scheduler](scheduler.md) | `cron`, `interval`, `ScheduledMixin` |
| [Cache](cache.md) | `cached`, `invalidate` |
| [Auth](auth.md) | `AuthBackend`, `AuthPayload`, `register_auth_backend`, `get_auth_backend` |
| [Manifest](manifest.md) | `PluginManifest`, `ResourceConfig`, `RuntimeConfig` |
| [Responses](responses.md) | `ok`, `error` |

---

## Full export list

```python
# Base classes
AutoMixin
TrustedBase
BasePlugin
ExecutionMode
PluginState

# Dispatch & routing
AutoDispatchMixin
RoutedPlugin
RouterRegistry
action
route

# Payload & access
schema
validate_payload
require_service
trusted
sandboxed

# Events & hooks
EventMixin
HookMixin
Event
HookResult
on_event
on_hook

# Observability
ObservabilityMixin
get_logger
traced
counted
timed
health_check

# Scheduler
ScheduledMixin
cron
interval

# Cache
cached
invalidate

# DB adapters
BaseAsyncRepository
BaseSyncRepository
BaseMongoRepository
BaseRedisRepository

# Auth
AuthBackend
AuthPayload
register_auth_backend
unregister_auth_backend
get_auth_backend
has_auth_backend

# RBAC
RBACChecker
require_permission
require_role
PermissionDenied

# Manifest types
PluginManifest
ResourceConfig
RuntimeConfig

# Responses
ok
error
```
