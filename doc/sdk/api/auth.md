---
title: Auth
description: AuthBackend, AuthPayload, RBAC decorators, and auth backend registration.
icon: material/lock-open
---

# Auth

xcoreSDK exposes the kernel's authentication backend interface, allowing plugins to register custom authentication providers and query authentication state.

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

Dataclass representing an authenticated identity.

```python
from xcore.sdk import AuthPayload

payload = AuthPayload(
    subject="user:abc123",       # unique identity string
    roles=["admin", "viewer"],   # role list
    claims={"org": "acme"},      # arbitrary key-value claims
)

payload.subject   # str
payload.roles     # list[str]
payload.claims    # dict
```

---

## AuthBackend

Abstract base class for implementing custom authentication backends.

```python
from xcore.sdk import AuthBackend, AuthPayload

class JWTAuthBackend(AuthBackend):

    async def authenticate(self, token: str) -> AuthPayload | None:
        """Validate token and return identity, or None if invalid."""
        try:
            data = jwt.decode(token, self.secret, algorithms=["HS256"])
            return AuthPayload(
                subject=data["sub"],
                roles=data.get("roles", []),
                claims=data,
            )
        except jwt.InvalidTokenError:
            return None

    async def refresh(self, payload: AuthPayload) -> str:
        """Issue a new token from an existing valid payload."""
        ...
```

### Required methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `authenticate` | `(token: str) → AuthPayload \| None` | Validate credential, return identity or `None` |
| `refresh` | `(payload: AuthPayload) → str` | Issue a refreshed credential |

---

## register_auth_backend

Registers an `AuthBackend` instance with the kernel.

```python
from xcore.sdk import register_auth_backend

class Plugin(AutoMixin):
    async def on_load(self) -> None:
        await super().on_load()
        register_auth_backend("jwt", JWTAuthBackend(secret=self.ctx.env["JWT_SECRET"]))
```

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `name` | `str` | Backend identifier |
| `backend` | `AuthBackend` | Backend instance |

---

## unregister_auth_backend

Removes a previously registered backend. Call from `on_unload` to avoid dangling references.

```python
async def on_unload(self) -> None:
    await super().on_unload()
    unregister_auth_backend("jwt")
```

---

## get_auth_backend

Retrieves a registered backend by name. Raises `KeyError` if not registered.

```python
backend = get_auth_backend("jwt")
payload = await backend.authenticate(token)
```

---

## has_auth_backend

Checks whether a backend is registered without raising.

```python
if has_auth_backend("jwt"):
    backend = get_auth_backend("jwt")
```

---

## RBAC

For role-based access control, see the RBAC decorators exposed from the kernel:

```python
from xcore.sdk import RBACChecker, require_permission, require_role, PermissionDenied
```

| Export | Description |
|--------|-------------|
| `RBACChecker` | Evaluates role/permission rules against an `AuthPayload` |
| `require_permission` | Decorator: raises `PermissionDenied` if permission absent |
| `require_role` | Decorator: raises `PermissionDenied` if role absent |
| `PermissionDenied` | Exception raised by RBAC checks |
