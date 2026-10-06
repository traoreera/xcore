---
title: Auth
description: AuthBackend, AuthPayload, RBAC decorators, and the IPC user-resolution flow.
icon: material/lock-open
---

# Auth

xcore exposes a kernel-level authentication backend interface: plugins register a single `AuthBackend` implementation, and the kernel (HTTP routes, and now IPC calls) can query it to resolve the identity behind a call — without knowing anything about JWTs, sessions, or whatever credential scheme the backend actually implements.

```python
from xcore.sdk import (
    AuthBackend,
    AuthPayload,
    register_auth_backend,
    unregister_auth_backend,
    get_auth_backend,
    has_auth_backend,
)
```

---

## AuthPayload

A `TypedDict` representing an authenticated identity. Returned by `AuthBackend.decode_token()`.

```python
from xcore.kernel.api.auth import AuthPayload

payload: AuthPayload = {
    "sub": "user:abc123",            # unique identity string — required
    "roles": ["admin", "viewer"],    # optional
    "permissions": ["write:users"],  # optional
    "user": {"org": "acme"},         # optional, arbitrary extra data
}
```

Only `sub` is required; `roles`, `permissions`, and `user` are optional (`NotRequired`).

---

## AuthBackend

`Protocol` that a plugin implements to become the active auth backend. No base class to inherit — any object with these three async methods satisfies it.

```python
from xcore.kernel.api.auth import AuthBackend, AuthPayload

class JWTAuthBackend:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    async def decode_token(self, token: str) -> AuthPayload | None:
        """Validate a token and return the identity, or None if invalid."""
        try:
            data = jwt.decode(token, self.secret, algorithms=["HS256"])
            return {"sub": data["sub"], "roles": data.get("roles", [])}
        except jwt.InvalidTokenError:
            return None

    async def extract_token(self, request) -> str | None:
        """Pull the raw token out of an incoming HTTP request."""
        header = request.headers.get("authorization", "")
        if header.startswith("Bearer "):
            return header[len("Bearer "):]
        return None

    async def has_permission(self, payload: AuthPayload, permission: str) -> bool:
        return permission in payload.get("roles", []) or permission in payload.get("permissions", [])
```

| Method | Signature | Description |
|--------|-----------|--------------|
| `decode_token` | `(token: str) → AuthPayload \| None` | Validate a raw token, return the identity or `None` |
| `extract_token` | `(request) → str \| None` | Pull the raw token out of an HTTP request (headers/cookies/query params) |
| `has_permission` | `(payload: AuthPayload, permission: str) → bool` | Check a single permission/role against a resolved identity |

---

## register_auth_backend / unregister_auth_backend

Registers the single active backend instance. There is no name/registry — one backend at a time per process.

```python
from xcore.sdk import register_auth_backend, unregister_auth_backend

class Plugin(TrustedBase):
    async def on_load(self) -> None:
        self._backend = JWTAuthBackend(secret=self.ctx.env["JWT_SECRET"])
        register_auth_backend(self._backend)

    async def on_unload(self) -> None:
        unregister_auth_backend()
```

`register_auth_backend` raises `TypeError` if the object doesn't structurally satisfy `AuthBackend` (missing one of the three methods).

---

## get_auth_backend / has_auth_backend

```python
from xcore.sdk import get_auth_backend, has_auth_backend

if has_auth_backend():
    backend = get_auth_backend()
    payload = await backend.decode_token(token)
```

`get_auth_backend()` returns `None` (never raises) when no backend is registered — every consumer in the kernel (RBAC, IPC resolution) treats "no backend" as a no-op, not an error.

---

## RBAC on HTTP routes

For role/permission checks on `@route`-declared HTTP endpoints:

```python
from xcore.kernel.api.rbac import RBACChecker, require_permission, require_role, get_current_user
```

| Export | Description |
|--------|-------------|
| `RBACChecker` | FastAPI dependency — resolves the user via the registered backend and checks required roles/permissions |
| `require_permission(*perms)` | Shortcut: `RBACChecker(list(perms))` |
| `require_role(*roles)` | Shortcut: `RBACChecker(list(roles))` |
| `get_current_user` | FastAPI dependency — just resolves and returns the `AuthPayload`, no check |

`RBACChecker` raises `HTTPException(503)` if no backend is registered (or passes through with `strict=False`), `401` if no/invalid token, `403` if required roles/permissions are missing. This only applies to routes declared with `@route(..., permissions=[...])` — see [`RoutedPlugin.get_router()`](./decorators.md#route).

---

## Resolving the current user on IPC calls

Separately from the HTTP-route RBAC above, the **IPC call path** (`supervisor.call()` / `TrustedBase.call_plugin()`) resolves the calling user and makes it available to plugin code, via the same registered `AuthBackend` — without requiring `@route`.

This is resolution only — it does not enforce anything by itself. The goal is to make "who is calling" available to plugin logic and to a future per-action permission check (`@action(permissions=[...])`, see [@action](./decorators.md#action)), while leaving existing behavior (requests with no backend registered, or no token) completely unaffected.

### How a token becomes a principal

1. The generic HTTP endpoint `POST /{plugin}/{action}` ([`router.py`](../../advanced/middleware.md)) calls `resolve_principal_from_request(request)`, which does the only two calls into the backend that happen for a given incoming request:
   ```python
   token = await backend.extract_token(request)   # read headers/cookies
   principal = await backend.decode_token(token)  # token → AuthPayload
   ```
   Best-effort: returns `None` without raising if there's no backend, no token, or an invalid token.
2. The resolved `principal` (an `AuthPayload` or `None`) travels as a kwarg through `supervisor.call(..., principal=principal)`.
3. Inside the middleware pipeline, `AuthResolverMiddleware` sits just before `PermissionMiddleware`. If `principal` is already set, it passes through unchanged — **the backend is never contacted twice for the same call**. It only calls `decode_token()` itself when it receives a raw `token=` kwarg instead of an already-resolved `principal`.
4. `PluginSupervisor._dispatch()` stores `principal` in a `ContextVar` (`_current_principal`, same pattern as the tenant-id ContextVar) for the duration of the call — never by mutating the plugin's shared `PluginContext`.
5. Plugin code reads it with `get_current_principal()`.
6. When a plugin calls another plugin via `self.call_plugin(...)`, the current principal is forwarded automatically — the nested call does **not** re-contact the auth backend:
   ```python
   # TrustedBase.call_plugin() — automatic, nothing to do in plugin code
   principal=get_current_principal()
   ```

### Diagram

```mermaid
sequenceDiagram
    participant C as HTTP client
    participant R as router.call_plugin()
    participant AB as AuthBackend (plugin auth)
    participant MW as AuthResolverMiddleware
    participant S as supervisor._dispatch()
    participant PA as Plugin A .handle()
    participant PB as Plugin B .handle()

    C->>R: POST /plugin_a/action (Authorization: Bearer xxx)
    R->>AB: extract_token(request)
    AB-->>R: "xxx"
    R->>AB: decode_token("xxx")
    AB-->>R: AuthPayload {sub, roles, permissions}
    R->>S: supervisor.call(..., principal=AuthPayload)
    S->>MW: pipeline.execute(..., principal=AuthPayload)
    Note over MW: principal already resolved → backend NOT called again
    MW->>S: next_call(..., principal=AuthPayload)
    S->>S: _current_principal.set(AuthPayload)
    S->>PA: handle(action, payload)
    PA->>PA: get_current_principal() → AuthPayload
    PA->>PB: call_plugin("plugin_b", "other_action")
    Note over PA,PB: principal=get_current_principal() propagated automatically
    PB->>MW: pipeline.execute(..., principal=AuthPayload)
    MW->>S: next_call(...)
    S->>PB: handle(...)
    PB->>PB: get_current_principal() → same AuthPayload
```

### Reading the principal in a plugin

```python
from xcore.kernel.api.auth import get_current_principal

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        principal = get_current_principal()
        if principal is None:
            # no backend registered, or no token on this call — not an error
            self.logger.debug("appel anonyme", action=action)
        else:
            self.logger.info("appel authentifié", sub=principal.get("sub"), action=action)
        ...
```

### What this does *not* do (yet)

- No action is blocked based on `principal` today — `@action(permissions=[...])` only stores the requirement on the function (`fn._xcore_action_permissions`); nothing in the kernel reads it yet.
- `PermissionEngine` / `PolicySet` (plugin-to-plugin resource ACL, see [Permissions & Policies](../../plugins/permissions.md)) is a separate system and is not merged with this — it still answers "can plugin A call plugin B", not "does this user have this role".
- If no plugin has called `register_auth_backend(...)`, every `principal` is always `None`, silently — no error, no behavior change versus before this feature existed.
