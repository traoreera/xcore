# Event & Hook System

XCore provides two mechanisms for decoupled communication: **Events** (asynchronous, side-effect based) and **Hooks** (synchronous, data-transformation based).

---

## 1. Asynchronous Events

The Event Bus is used for "fire-and-forget" communication. It is perfect for triggering side effects like logging, sending emails, or updating caches after an action occurs.

### Key Concepts
-   **Priority**: Handlers with higher numbers (e.g., 100) run before those with lower numbers (e.g., 50).
-   **Propagation**: A handler can call `event.stop_propagation()` to prevent others from receiving it.
-   **Gather**: By default, multiple handlers run in parallel using `asyncio.gather`.

### Example: Subscribing to User Creation
```python
@on("user.created", priority=100)
async def log_creation(self, event):
    self.logger.info(f"New user created: {event.data['id']}")
```

---

## 2. Built-in System Events

XCore emits several built-in events that you can subscribe to:

| Event Name | Description | Payload |
| :--- | :--- | :--- |
| `xcore.plugins.booted` | Emitted when all plugins are loaded. | `{"report": {...}}` |
| `plugin.<name>.loaded` | Emitted when a specific plugin is loaded. | `{"name": "...", "version": "..."}` |
| `plugin.<name>.reloaded` | Emitted after a successful hot reload. | `{"name": "..."}` |
| `plugin.<name>.unloaded` | Emitted after a plugin is unloaded. | `{"name": "..."}` |
| `permission.deny` | Emitted on every denied permission check. | `{"plugin": "...", "resource": "...", "action": "..."}` |
| `security.violation` | Emitted when a security scan fails. | `{"plugin": "...", "errors": [...]}` |

---

## 3. Best Practices for Events

1.  **Avoid Long-Running Tasks**: Event handlers run in the main event loop. For heavy tasks, delegate to the `scheduler`.
2.  **Use Priorities Wisely**: Use high priorities (100+) for logging, and default priorities (50) for business logic.
3.  **Deduplication**: If your application runs in multiple instances, remember that events are local to the instance unless you use a distributed event bus.
4.  **Always Cleanup**: If you manually subscribe outside the plugin lifecycle, ensure you unsubscribe to prevent memory leaks.

---

## 4. Synchronous Hooks

Hooks allow you to modify data or perform synchronous actions during a specific process. They are managed by the `HookManager`.

### A. Filters (Data Transformation)
Filters allow you to "pass a value through a chain" to let other plugins modify it.

```python
# Kernel or Plugin side
title = self.ctx.hooks.apply_filters("page_title", "Welcome to XCore")

# Another Plugin side
@filter("page_title")
def modify_title(self, title):
    return f"{title} | Dashboard"
```

### B. Actions (Side Effects)
Actions are synchronous side effects that don't return a value.

```python
# Kernel or Plugin side
self.ctx.hooks.do_action("before_render", template="index.html")

# Another Plugin side
@action_hook("before_render")
def on_render(self, template):
    print(f"Rendering {template}")
```

---

## 5. Difference Between Events and Hooks

| Feature | Events | Hooks |
| :--- | :--- | :--- |
| **Execution** | Asynchronous (`async`) | Synchronous (`def`) |
| **Returns Value?** | No | Yes (Filters) |
| **Parallel?** | Yes | No (Sequential) |
| **Use Case** | Decoupled side effects. | Data modification / Inline logic. |
