---
title: Action & Route Decorators
description: "@action, @route, @schema, @validate_payload, @require_service, @trusted, @sandboxed."
icon: material/tag-multiple
---

# Decorators

All action and route decorators are importable from `xcore.sdk`.

---

## @action

Registers an async method as a dispatchable action.

```python
from xcore.sdk import action

@action("get_user")
async def get_user(self, payload: dict) -> dict:
    ...
```

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `name` | `str` | Action identifier used in `handle(name, payload)` |

The decorated method must be `async`, accept `self` and `payload: dict`, and return a `dict`.

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

The schema is stored on the function as `fn._xcore_schema`:

```python
{
    "version": "2.0",
    "input": {"email": "str", "role": "str"},
    "output": {"user_id": "int", "created_at": "str"},
    "deprecated_fields": {},
    "breaking_since": None,
    "description": "Create a new user account",
}
```

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
@traced("span")                          # observability wrapper
@counted("metric")                       # counter wrapper
@cached(ttl=300, key=…)                  # innermost — cache lookup
async def handler(self, payload: dict) -> dict:
    ...
```

Decorators execute **bottom-up** at call time. The order above ensures: cache check → tracing → service check → validation → mode enforcement → action dispatch.

!!! tip
    Use either `@schema(type_response="dict")` **or** `@validate_payload` — not both. `@schema` wraps `@validate_payload` internally when `type_response != "_"`.
