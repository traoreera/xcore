---
title: Responses
description: ok() and error() helpers for consistent action response formatting.
icon: material/arrow-collapse-down
---

# Responses

xcoreSDK provides two helpers for building consistent action response dicts: `ok()` for success and `error()` for failure.

```python
from xcore.sdk import ok, error
```

---

## ok

Returns a success response dict.

```python
from xcore.sdk import ok

return ok(user={"id": "abc", "name": "Alice"})
# → {"status": "ok", "user": {"id": "abc", "name": "Alice"}}

return ok()
# → {"status": "ok"}

return ok(created=True, user_id="abc123")
# → {"status": "ok", "created": True, "user_id": "abc123"}
```

**Signature**

```python
def ok(**kwargs) -> dict:
    return {"status": "ok", **kwargs}
```

All keyword arguments are merged into the response dict alongside `"status": "ok"`.

---

## error

Returns an error response dict.

```python
from xcore.sdk import error

return error("id requis", "missing_id")
# → {"status": "error", "message": "id requis", "code": "missing_id"}

return error("Rate limit exceeded", "rate_limited")
# → {"status": "error", "message": "Rate limit exceeded", "code": "rate_limited"}
```

**Signature**

```python
def error(message: str, code: str = "error") -> dict:
    return {"status": "error", "message": message, "code": code}
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `message` | `str` | — | Human-readable error description |
| `code` | `str` | `"error"` | Machine-readable error code |

---

## Response shape

All action handlers should return one of these shapes:

```python
# Success
{"status": "ok", ...}

# Error
{"status": "error", "message": "...", "code": "..."}
```

The kernel and any caller can pattern-match on `result["status"]` to determine success.

---

## Common error codes

| Code | Meaning |
|------|---------|
| `missing_id` | Required ID field not present in payload |
| `validation_error` | Pydantic validation failed (`@validate_payload`) |
| `not_found` | Entity does not exist |
| `permission_denied` | Caller lacks required permission |
| `rate_limited` | Rate limit exceeded |
| `send_failed` | External call (email, webhook) failed |
| `service_unavailable` | Required service not registered |

These are conventions — any string is a valid error code.

---

## Example

```python
@action("get_user")
async def get_user(self, payload: dict) -> dict:
    user_id = payload.get("id")
    if not user_id:
        return error("id is required", "missing_id")

    user = await self._repo.get_by_id(user_id)
    if user is None:
        return error(f"user {user_id} not found", "not_found")

    return ok(user=user)
```
