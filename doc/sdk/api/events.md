---
title: Events & Hooks
description: "@on_event, @on_hook, EventMixin, HookMixin, Event, and HookResult."
icon: material/broadcast
---

# Events & Hooks

xcoreSDK provides two asynchronous pub/sub mechanisms:

- **Events** — broadcast notifications. Any plugin can subscribe; all subscribers receive the event.
- **Hooks** — interceptor pipeline. Handlers run in priority order; a handler can stop propagation.

---

## @on_event

Subscribes an async method to a named event pattern.

```python
from xcore.sdk import on_event, Event

@on_event("user.created")
async def on_user_created(self, event: Event) -> None:
    self.logger.info("new user: %s", event.data.get("user_id"))
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `event_name` | `str` | — | Event name or glob pattern (`user.*`, `*.created`) |
| `priority` | `int` | `50` | Execution priority; higher numbers run first |
| `once` | `bool` | `False` | Auto-unsubscribe after first delivery |

### Wildcard patterns

```python
@on_event("user.*")          # all user.X events
@on_event("*.created")       # any X.created event
@on_event("system.shutdown", once=True)  # fires once, then unregisters
```

---

## @on_hook

Registers an async method as a hook handler. Hooks differ from events in that they run sequentially in priority order and can carry a result or block propagation.

```python
from xcore.sdk import on_hook, Event

@on_hook("plugin.*.loaded", priority=10)
async def after_plugin_load(self, event: Event) -> None:
    self.logger.debug("plugin loaded: %s", event.data.get("plugin"))
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `hook_name` | `str` | — | Hook name or glob pattern |
| `priority` | `int` | `50` | Execution order; lower numbers run first |
| `once` | `bool` | `False` | Auto-unregister after first call |
| `timeout` | `float \| None` | `None` | Per-handler timeout in seconds |

---

## Event

`Event` is the object passed to all event and hook handlers.

```python
from xcore.sdk import Event

async def handler(self, event: Event) -> None:
    event.name     # str — event name as emitted
    event.data     # dict — arbitrary payload
    event.source   # str | None — emitting plugin name
```

---

## HookResult

Returned by hook handlers to signal success, failure, or propagation control.

```python
from xcore.sdk import HookResult

# Implicit — just return None from the handler
# Explicit — stop propagation
return HookResult(stop=True)
```

---

## EventMixin

Registered automatically by `AutoMixin`. Scans the plugin class for `@on_event`-decorated methods and subscribes them to `self.ctx.events` during `on_load`.

You rarely need to interact with `EventMixin` directly — use `@on_event` on your methods and `AutoMixin` handles the rest.

### Manual emit

To emit events from within a plugin:

```python
await self.ctx.events.emit("user.created", {
    "user_id": "abc",
    "email": "user@example.com",
})
```

---

## HookMixin

Registered automatically by `AutoMixin`. Scans for `@on_hook`-decorated methods and registers them with `self.ctx.hooks` during `on_load`.

All hook registrations are cleaned up automatically in `on_unload`.
