---
title: Action & Route Decorators
description: "@action, @route, @schema, @validate_payload, @require_service, @trusted, @sandboxed."
icon: material/tag-multiple
---

# Decorators

All action and route decorators are importable from `xcore.sdk`.

---

## @action

Registers an async method as a dispatchable action, resolved by `AutoDispatchMixin.handle(action_name, payload)`.

```python
from xcore.sdk import action

@action("get_user")
async def get_user(self, payload: dict) -> dict:
    ...
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | — | Action identifier used in `handle(name, payload)` |
| `permissions` | `list[str] \| None` | `None` | Roles/permissions required to invoke this action — **all** of them (AND). Stored on `fn._xcore_action_permissions`, enforced by `ActionPermissionMiddleware` against the `principal` resolved by `AuthResolverMiddleware` (see [Auth: Enforcing action permissions](./auth.md#enforcing-action-permissions)). No `principal` with a declared requirement is a denial (fail-closed). |
| `permission_groups` | `list[list[str]] \| None` | `None` | Alternative permission groups — satisfied if the principal fully covers **at least one** group (OR of AND). For a role hierarchy where several distinct permissions each grant sufficient access on their own (e.g. a tenant owner *or* a platform admin) — `permissions` alone can't express that, it would require both. Independent and combinable with `permissions`: if both are set, `permissions` must be fully satisfied *and* at least one group must be too. |
| `side_effect` | `"read" \| "write" \| "outbound" \| None` | `None` | Declares how consequential the action is — orthogonal to `permissions`: `permissions` says *who* can call it, `side_effect` says *what risk* it carries once the call is authorized. Purely declarative — the kernel does nothing with it itself; it's for an external consumer (e.g. a bridge exposing actions as LLM tools) to decide whether an action can be a direct tool or needs human approval first. Raises `ValueError` at decoration time if given anything other than one of the three values. An action without a declared `side_effect` should be treated by such a consumer as the riskiest tier — no declaration is not an implicit green light. |

The decorated method must be `async`, accept `self` and `payload: dict`, and return a `dict`.

```python
@action("team_report", permission_groups=[["tenants:write"], ["admin:*"]])
async def team_report(self, payload: dict) -> dict:
    # allowed for the tenant owner (tenants:write) OR a platform admin
    # (admin:*) — never both required at once.
    ...

@action("send_email", permissions=["admin"], side_effect="outbound")
async def send_email(self, payload: dict) -> dict:
    ...
```

`@action` and `@schema` are fully independent decorators — stack them (in either order) when an action also needs a versioned schema:

```python
@action("create_user", permissions=["admin"])
@schema(version="2.0", input={"email": (str, ...)})
async def create_user(self, payload: dict) -> dict: ...
```

### Reading permissions/side_effect without a live plugin instance

Both `fn._xcore_action_permissions`/`_xcore_action_permission_groups`/`_xcore_action_side_effect` (read per-call by `ActionPermissionMiddleware` via `LifecycleManager.get_action_permissions()`/`get_action_permission_groups()`, which need a loaded plugin instance) **and** a mirror of all three on `SchemaRegistry`'s `ActionSchema` (see [Schema metadata](#schema-metadata)) are populated — the registry entry exists for *every* `@action`, with or without `@schema`, specifically so an external consumer can read permissions and schema for the whole system from `schema_registry` alone, without instantiating each plugin's `LifecycleManager`.

---

## @route

Registers an async method as a FastAPI route, exposed under the plugin's URL prefix.

```python
from xcore.sdk import route

@route("/users/{user_id}", method="GET", tags=["users"], summary="Get user")
async def route_get_user(self, user_id: str):
    ...
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `path` | `str` | — | URL path, supports FastAPI path parameters |
| `method` | `str` | `"GET"` | HTTP method |
| `tags` | `list[str]` | `[]` | OpenAPI tags |
| `summary` | `str` | `""` | OpenAPI summary |
| `status_code` | `int` | `200` | Default response status code |
| `permissions` | `list[str]` | `[]` | Required permission strings |

Path parameters become method arguments by name. Request bodies are `body: dict`.

```python
@route("/items", method="POST", status_code=201)
async def create_item(self, body: dict):
    return await self.create_action(body)
```

---

## @schema

Declares a versioned schema for an action — stores it on `fn._xcore_schema` for the SchemaRegistry — and optionally applies `@validate_payload` automatically.

Independent from `@action`: it can be stacked under `@action` in either order, or used alone on a method that isn't a dispatchable action at all (the schema metadata is just attached to the function; `AutoDispatchMixin` only registers it in the `SchemaRegistry` when `_xcore_action` is also present).

```python
from xcore.sdk import action, schema

@action("create_user")
@schema(
    version="2.0",
    input={"email": (str, ...), "role": (str, "user")},
    output={"user_id": int, "created_at": str},
    description="Create a new user account",
    type_response="dict",
)
async def create_user(self, payload: dict) -> dict:
    # payload is already validated when type_response != "_"
    email = payload["email"]
    ...
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `version` | `str` | — | Schema version string (semver recommended) |
| `input` | `dict \| None` | `None` | Input field definitions (see field syntax below) |
| `output` | `dict \| None` | `None` | Output field definitions (documentation only) |
| `deprecated_fields` | `dict[str, str] \| None` | `None` | Map of deprecated field name → migration message |
| `breaking_since` | `str \| None` | `None` | Version at which a breaking change was introduced |
| `description` | `str` | `""` | Human-readable description stored in the schema |
| `validate` | `bool` | `True` | Whether to apply `@validate_payload` automatically |
| `type_response` | `"dict"`, `"model"`, `"_"` | `"_"` | Controls what the handler receives (see below) |
| `unset` | `bool` | `False` | If `True`, excludes unset fields from `model_dump()` |

### Input field syntax

Follows Pydantic `create_model` conventions:

```python
input={
    "email": str,              # required — shorthand for (str, ...)
    "email": (str, ...),       # required — explicit
    "role":  (str, "user"),    # optional with default "user"
    "age":   (int, None),      # optional, defaults to None
}
```

### `type_response` values

| Value | Validation applied? | Handler receives |
|-------|--------------------|-|
| `"_"` | No | original `payload: dict` unchanged |
| `"dict"` | Yes | `validated.model_dump(exclude_unset=unset)` |
| `"model"` | Yes | Pydantic model instance |

When `type_response="dict"` or `"model"`, `@schema` internally applies `@validate_payload` — you do **not** need both decorators.

When `type_response="_"` (default), validation is skipped; `@schema` only stores the schema metadata. Use this to annotate schema without enforcing it.

### Schema metadata

The schema is stored on the function as `fn._xcore_schema`. `@schema` builds the pydantic model **once** from `input` (and once from `output`) and reuses that same model for both validation (via `@validate_payload` internally) and the JSON Schema below — it doesn't rebuild a separate model for each:

```python
{
    "version": "2.0",
    "input": {"email": "str", "role": "str"},        # {field: type name} — used by BreakingChangeDetector
    "output": {"user_id": "int", "created_at": "str"},
    "deprecated_fields": {},
    "breaking_since": None,
    "description": "Create a new user account",
    "input_json_schema": {                            # full JSON Schema from the real pydantic model
        "title": "DynamicSchema",
        "type": "object",
        "properties": {
            "email": {"title": "Email", "type": "string"},
            "role": {"title": "Role", "type": "string", "default": "user"},
        },
        "required": ["email"],
    },
    "output_json_schema": {"...": "same shape, from `output`"},
}
```

`input`/`output` stay flat `{field: type_name}` dicts — that's what `BreakingChangeDetector` compares field-by-field to flag breaking changes, and a full JSON Schema diff would be a different (stricter) comparison. `input_json_schema`/`output_json_schema` are for consumers that need the real shape (nested fields, defaults, constraints) — generating an LLM tool definition, OpenAPI, documentation — not just a type name. Both are `{}` when the corresponding `input`/`output` wasn't declared.

This is also mirrored on `SchemaRegistry`'s `ActionSchema.input_json_schema`/`.output_json_schema` (see [Reading permissions/side_effect without a live plugin instance](#reading-permissionsside_effect-without-a-live-plugin-instance)).

### Deprecation tracking

```python
@action("create_user")
@schema(
    version="3.0",
    input={"email": (str, ...), "role": (str, "user")},
    deprecated_fields={"username": "Removed in v2.0 — use email instead"},
    breaking_since="2.0",
)
async def create_user(self, payload: dict) -> dict:
    ...
```

### Replacing @validate_payload

`@schema` with `type_response="dict"` is a strict superset of `@validate_payload`:

```python
# These are equivalent:

@validate_payload({"email": (str, ...), "role": (str, "user")})
async def handler(self, payload: dict) -> dict: ...

@schema(version="1.0", input={"email": (str, ...), "role": (str, "user")}, type_response="dict")
async def handler(self, payload: dict) -> dict: ...
```

Use `@schema` when you need versioning or deprecation tracking; use `@validate_payload` when you just need runtime validation.

---

## @validate_payload

Validates `payload` against a Pydantic v2 model before calling the handler. On failure, returns an error response automatically.

```python
from xcore.sdk import validate_payload
from pydantic import BaseModel, Field

class CreateUserSchema(BaseModel):
    name: str = Field(..., min_length=2)
    email: str

@action("create_user")
@validate_payload(CreateUserSchema)
async def create_user(self, payload: dict) -> dict:
    # payload is already validated; invalid calls never reach here
    ...
```

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `schema` | `type[BaseModel]` | Pydantic model class |

On validation failure, returns `error("Validation error: ...", "validation_error")`.

!!! tip "Decorator position"
    `@validate_payload` should appear **above** `@require_service` in source code so validation runs before service checks.

---

## @require_service

Guards a handler behind a service availability check. Raises `KeyError` (or returns an error response) if the named service is not registered in `self.ctx.services`.

```python
from xcore.sdk import require_service

@action("fetch_data")
@require_service("db")
async def fetch_data(self, payload: dict) -> dict:
    db = self.get_service("db")
    ...
```

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `service_name` | `str` | Key in `self.ctx.services` |

---

## @retry

Automatically retries a failing async action with linear backoff. A silent no-op when applied to a synchronous function.

```python
from xcore.sdk import retry

@action("fetch_invoice")
@retry(max_attempts=3, backoff=0.5, exceptions=(IOError, TimeoutError))
@traced("fetch_invoice")
async def fetch_invoice(self, payload: dict) -> dict:
    # Will retry up to 3 times on IOError or TimeoutError
    return await self._external_api_call(payload["invoice_id"])
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `max_attempts` | `int` | `3` | Total number of attempts (including the first call) |
| `backoff` | `float` | `1.0` | Linear backoff multiplier in seconds. Delay = `backoff * attempt` |
| `exceptions` | `tuple[type[Exception], ...]` | `(Exception,)` | Exception types to catch and retry |
| `on_failure` | `callable \| None` | `None` | Called as `on_failure(self, payload, exc)` after the final failure. May be async |

On final failure, returns `error(str(exc), "retry_exhausted")`.

```python
async def _notify_on_failure(self, payload, exc):
    self.logger.error("toutes les tentatives ont échoué", erreur=str(exc))
    await self.ctx.events.emit("invoice.fetch_failed", {"error": str(exc)})

@action("fetch_invoice")
@retry(
    max_attempts=5,
    backoff=2.0,
    exceptions=(IOError,),
    on_failure=_notify_on_failure,
)
async def fetch_invoice(self, payload: dict) -> dict:
    ...
```

!!! tip "Position dans la pile de décorateurs"
    `@retry` doit être placé **entre** `@require_service` et `@traced` pour que chaque tentative soit tracée individuellement.

---

## @trusted

Restricts the action to plugins running in `trusted` execution mode. Returns a permission-denied response for sandboxed callers.

```python
from xcore.sdk import trusted

@action("admin_action")
@trusted
async def admin_action(self, payload: dict) -> dict:
    ...
```

No parameters.

---

## @sandboxed

Marks an action as safe to call from sandboxed plugins. Does not restrict trusted callers.

```python
from xcore.sdk import sandboxed

@action("public_ping")
@sandboxed
async def ping(self, payload: dict) -> dict:
    return ok(pong=True)
```

No parameters.

---

## Stacking order reference

```python
@action("name")                          # outermost — registers action
@trusted                                 # enforces execution mode
@schema(version="1.0", input={...},      # schema declaration + validation
        type_response="dict")            # (replaces @validate_payload)
@require_service("db")                   # checks service after validation
@retry(max_attempts=3, backoff=1.0)      # retries on transient failures
@traced("span")                          # observability wrapper
@counted("metric")                       # counter wrapper
@cached(ttl=300, key=…)                  # innermost — cache lookup
async def handler(self, payload: dict) -> dict:
    ...
```

Decorators execute **bottom-up** at call time. The order above ensures: cache check → tracing → retry → service check → validation → mode enforcement → action dispatch.

!!! tip
    Use either `@schema(type_response="dict")` **or** `@validate_payload` — not both. `@schema` wraps `@validate_payload` internally when `type_response != "_"`.
