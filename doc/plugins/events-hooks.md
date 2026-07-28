---
title: Events & Hooks
description: Advanced inter-plugin communication using the asynchronous EventBus and synchronous HookManager.
icon: material/transit-connection-variant
---

# Events & Hooks

Xcore provides two distinct systems for cross-plugin communication: **Events** for asynchronous, one-to-many broadcasting, and **Hooks** for synchronous result interception and processing.

---

### Key Concepts

#### Events (Asynchronous)
Events are used to notify other parts of the system that something has happened. They are non-blocking and support multiple subscribers.

- **`emit_sync()`**: Fire-and-forget. The event is scheduled in the background.
- **`emit()`**: Awaited. Completes when all subscribers have finished processing.
- **Wildcards**: Subscribe to `user.*` to catch `user.created` and `user.deleted`.

#### Hooks (Synchronous)
Hooks are used to intercept or modify the behavior of a specific action. They are synchronous and follow a strict "Interceptor" pattern.

- **Pre-interceptors**: Modify the payload before it reaches the target.
- **Post-interceptors**: Modify the result before it returns to the caller.
- **Result Processors**: Final transformation of the response.

---

### Practical Guide

#### 1. Working with Events

```python linenums="1" title="src/main.py"
class Plugin(TrustedBase):
    async def on_load(self):
        # Subscribe to user creation
        @self.ctx.events.on("user.created")
        async def handle_new_user(event):
            user_id = event.data["id"]
            await self.send_welcome_email(user_id)

    async def handle(self, action, payload):
        if action == "delete_user":
            # Broadcast the deletion
            self.ctx.events.emit_sync("user.deleted", {"id": payload["id"]})
            return ok()
```

#### 2. Working with Hooks

```python linenums="1" title="src/main.py"
class Plugin(TrustedBase):
    async def on_load(self):
        # Intercept the 'greet' action of the 'hello' plugin
        @self.ctx.hooks.on("plugin.hello.greet")
        def append_metadata(result):
            # Modify the result dictionary in place
            result["server_time"] = time.time()
            return result
```

---

### Comparison Table

| Feature | Events | Hooks |
|---------|--------|-------|
| **Execution** | Asynchronous (`async def`) | Synchronous (`def`) |
| **Blocking** | No (with `emit_sync`) | Yes (Sequential) |
| **Return Value**| None | Modified Result |
| **Subscribers** | Multiple | Multiple (Ordered) |
| **Use Case** | Analytics, Notifications | Result transformation, Logging |

---

### API Reference

#### `EventBus` (`self.ctx.events`)
| Method | Description |
|--------|-------------|
| `on(pattern)` | Decorator to subscribe to an event. |
| `emit(name, data)` | Emit and wait for all subscribers. |
| `emit_sync(name, data)`| Fire-and-forget emission. |

#### `HookManager` (`self.ctx.hooks`)
| Method | Description |
|--------|-------------|
| `on(name)` | Register a result interceptor. |
| `emit(name, result)` | Manually trigger hook processing for a result. |

---

### Common Errors & Pitfalls

!!! danger "Async in Hooks"
    The `HookManager` expects synchronous functions. Attempting to use `async def` as a hook handler will result in the `coroutine` object being returned in the response instead of the actual data.
    **Fix**: Use `EventBus` if you need to perform asynchronous work.

!!! warning "Circular Events"
    If Plugin A emits `event.a` and Plugin B listens to it and emits `event.b`, while Plugin A listens to `event.b`, you can create an infinite loop.
    **Fix**: Use unique namespaces and avoid "ping-pong" event patterns.

!!! failure "Wildcard Performance"
    Subscribing to `*` (everything) will trigger your handler for every single event in the system, including kernel internal events. This can significantly impact performance.

---

### Best Practices

!!! success "Use Priority for Hooks"
    When registering multiple hooks for the same action, use the `priority` argument (default: 100) to control the order of execution. Lower numbers run first.

!!! tip "Events for Logging"
    Use `emit_sync()` for all logging and telemetry events. This ensures that the main request flow is never delayed by observability tasks.
