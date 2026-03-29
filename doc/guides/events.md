# Event System

XCore features a powerful, high-performance, and asynchronous **Event Bus** that enables decoupled communication between the kernel, services, and plugins.

## 1. What is the Event Bus?

The Event Bus acts as a central hub for all system and application-level events. It allows one component to "emit" an event and multiple other components to "subscribe" to it, without knowing each other's implementation.

## 2. Key Features

-   **Asynchronous Execution**: Handlers can be asynchronous (`async def`) and are executed in the main event loop.
-   **Priorities**: Control the order of execution for multiple handlers (higher numbers run first).
-   **One-Shot Handlers**: Automatically unsubscribe after the first event is handled.
-   **Propagation Control**: Prevent an event from reaching subsequent handlers.
-   **System-Level Events**: Built-in events for plugin lifecycle, security, and health.

## 3. Emitting Events

You can emit events from any plugin or service that has access to the kernel's event bus (`self.ctx.events`).

```python
# In a plugin class
async def some_action(self):
    data = {"user_id": 123, "action": "login"}

    # Standard emit (asynchronous)
    await self.ctx.events.emit("user.login", data)

    # Synchronous fire-and-forget
    self.ctx.events.emit_sync("user.login", data)
```

## 4. Subscribing to Events

Plugins can subscribe to events during their `on_load` phase.

### Using Decorators

```python
class MyPlugin(TrustedBase):

    @on("user.login", priority=100)
    async def on_user_login(self, event):
        print(f"High-priority handler: {event.data['user_id']}")

    @once("system.ready")
    async def on_ready(self, event):
        print("System is ready! This runs only once.")
```

### Manual Subscription

```python
class MyPlugin(TrustedBase):
    async def on_load(self) -> None:
        self.ctx.events.subscribe("user.login", self._handle_login, priority=50)

    async def _handle_login(self, event):
        print(f"Processing login: {event.data['user_id']}")
```

## 5. Event Objects

Handlers receive an `Event` object with the following properties:

-   **`name`**: The name of the event (e.g., `user.login`).
-   **`data`**: A dictionary containing the event payload.
-   **`source`**: The name of the component that emitted the event (if provided).
-   **`cancelled`**: Boolean indicating if the event has been cancelled.
-   **`propagate`**: Boolean indicating if the event should continue to the next handler.

### Controlling Propagation

```python
async def on_user_login(self, event):
    # Stop other handlers from receiving this event
    event.stop_propagation()

    # Mark as cancelled (can be checked by other logic)
    event.cancel()
```

## 6. System Events

XCore emits several built-in events that you can subscribe to:

| Event Name | Description | Payload |
| :--- | :--- | :--- |
| `xcore.plugins.booted` | Emitted when all plugins are loaded. | `{"report": {...}}` |
| `plugin.<name>.loaded` | Emitted when a specific plugin is loaded. | `{"name": "...", "version": "..."}` |
| `plugin.<name>.reloaded` | Emitted after a successful hot reload. | `{"name": "..."}` |
| `plugin.<name>.unloaded` | Emitted after a plugin is unloaded. | `{"name": "..."}` |
| `permission.allow` | Emitted on every allowed permission check. | `{"plugin": "...", "resource": "...", "action": "..."}` |
| `permission.deny` | Emitted on every denied permission check. | `{"plugin": "...", "resource": "...", "action": "..."}` |
| `security.violation` | Emitted when a security scan fails. | `{"plugin": "...", "errors": [...]}` |

## 7. Best Practices

1.  **Use Priorities Wisely**: Use high priorities (100+) for logging, validation, or pre-processing, and default priorities (50) for core business logic.
2.  **Avoid Long-Running Tasks**: Event handlers run in the main event loop. For heavy tasks, delegate to a background worker or the `scheduler`.
3.  **Naming Conventions**: Use dot-separated lowercase strings (e.g., `order.created`, `payment.failed`).
4.  **One-Shot Subscriptions**: Use `once()` for initialization tasks that should only happen the first time an event is received.
5.  **Always Cleanup**: If you manually subscribe to events outside of the standard plugin lifecycle, ensure you unsubscribe to prevent memory leaks.
