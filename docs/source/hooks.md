# hooks - Hook System Module

## Overview

The `hooks` module provides an event-driven extensibility system. It allows plugins and core components to register callbacks that are triggered at specific points in the application lifecycle.

## Module Structure

```
hooks/
├── __init__.py          # Module exports
├── hooks.py             # Hook manager
└── utils.py             # Hook utilities
```

## Core Components

### HookManager

Central manager for registering and triggering hooks.

```python
class HookManager:
    """
    Event-driven hook system for extensibility.

    Supports:
    - Pre/post hooks
    - Priority-based execution
    - Async and sync handlers
    - Filter hooks
    - Action hooks
    """

    def __init__(self):
        self._hooks: Dict[str, List[Hook]] = {}
        self._filters: Dict[str, List[Filter]] = {}

    # Action hooks (trigger events)
    def register(
        self,
        hook_name: str,
        handler: Callable,
        priority: int = 10
    ) -> None:
        """
        Register a handler for a hook.

        Args:
            hook_name: Name of the hook event
            handler: Function to call when hook fires
            priority: Execution priority (lower = earlier)
        """

    def unregister(
        self,
        hook_name: str,
        handler: Callable
    ) -> None:
        """Unregister a handler from a hook."""

    async def do_action(
        self,
        hook_name: str,
        *args,
        **kwargs
    ) -> None:
        """
        Trigger an action hook.

        Args:
            hook_name: Name of the hook to trigger
            *args: Positional arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
        """

    # Filter hooks (modify data)
    def add_filter(
        self,
        filter_name: str,
        handler: Callable,
        priority: int = 10
    ) -> None:
        """
        Register a filter handler.

        Args:
            filter_name: Name of the filter
            handler: Function to modify data
            priority: Execution priority
        """

    def remove_filter(
        self,
        filter_name: str,
        handler: Callable
    ) -> None:
        """Remove a filter handler."""

    async def apply_filters(
        self,
        filter_name: str,
        value: Any,
        *args,
        **kwargs
    ) -> Any:
        """
        Apply all filters to a value.

        Args:
            filter_name: Name of the filter
            value: Value to filter
            *args: Additional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Filtered value
        """

    # Utility methods
    def has_action(self, hook_name: str) -> bool:
        """Check if a hook has registered handlers."""

    def has_filter(self, filter_name: str) -> bool:
        """Check if a filter has registered handlers."""

    def remove_all_actions(self, hook_name: str = None) -> None:
        """Remove all action handlers."""

    def remove_all_filters(self, filter_name: str = None) -> None:
        """Remove all filter handlers."""
```

### Decorators

```python
def action(hook_name: str, priority: int = 10):
    """
    Decorator to register an action hook.

    Usage:
        @action("user.created", priority=5)
        async def send_welcome_email(user):
            await email_service.send(user.email, "Welcome!")
    """

def filter(filter_name: str, priority: int = 10):
    """
    Decorator to register a filter.

    Usage:
        @filter("user.name", priority=10)
        def capitalize_name(name, user):
            return name.title()
    """
```

## Built-in Hooks

### Application Lifecycle

| Hook | When Triggered | Arguments |
|------|----------------|-----------|
| `app.startup` | Application starts | `app` |
| `app.shutdown` | Application stops | `app` |
| `app.ready` | All plugins loaded | `app` |

### Request/Response

| Hook | When Triggered | Arguments |
|------|----------------|-----------|
| `request.start` | Request received | `request` |
| `request.end` | Response sent | `request`, `response` |
| `request.error` | Exception raised | `request`, `exception` |

### User Management

| Hook | When Triggered | Arguments |
|------|----------------|-----------|
| `user.created` | User registered | `user` |
| `user.updated` | User modified | `user`, `changes` |
| `user.deleted` | User removed | `user_id` |
| `user.login` | User logged in | `user`, `token` |
| `user.logout` | User logged out | `user` |

### Plugin Lifecycle

| Hook | When Triggered | Arguments |
|------|----------------|-----------|
| `plugin.installing` | Before plugin install | `plugin_info` |
| `plugin.installed` | After plugin install | `plugin` |
| `plugin.enabling` | Before plugin enable | `plugin` |
| `plugin.enabled` | After plugin enable | `plugin` |
| `plugin.disabling` | Before plugin disable | `plugin` |
| `plugin.disabled` | After plugin disable | `plugin` |
| `plugin.uninstalling` | Before plugin uninstall | `plugin` |
| `plugin.uninstalled` | After plugin uninstall | `plugin_info` |

### Database

| Hook | When Triggered | Arguments |
|------|----------------|-----------|
| `db.migrate.before` | Before migration | `revision` |
| `db.migrate.after` | After migration | `revision` |

## Usage Examples

### Basic Action Hook

```python
from hooks import hook_manager, action

# Register using manager
async def log_user_creation(user):
    print(f"New user created: {user.email}")

hook_manager.register("user.created", log_user_creation)

# Or use decorator
@action("user.created")
async def send_welcome_email(user):
    await email_service.send(
        to=user.email,
        subject="Welcome!",
        body="Thanks for joining!"
    )

# Trigger the hook
await hook_manager.do_action("user.created", new_user)
```

### Filter Hook

```python
from hooks import hook_manager, filter

# Add filter
@filter("user.name")
def capitalize_name(name, user=None):
    return name.title()

@filter("user.name")
def remove_special_chars(name, user=None):
    return re.sub(r'[^\w\s]', '', name)

# Apply filters
formatted_name = await hook_manager.apply_filters(
    "user.name",
    "john doe!!!",
    user=user
)
# Result: "John Doe"
```

### Priority-Based Execution

```python
from hooks import action

# Higher priority (lower number) runs first
@action("app.startup", priority=1)
async def load_config_first(app):
    """Load configuration"""
    pass

@action("app.startup", priority=5)
async def setup_database(app):
    """Setup database (depends on config)"""
    pass

@action("app.startup", priority=10)
async def load_plugins(app):
    """Load plugins (depends on database)"""
    pass
```

### Plugin Integration

```python
# In plugin run.py
from hooks import action, filter

class Plugin:
    def on_enable(self):
        # Register hooks when enabled
        action("user.created", self.on_user_created, priority=10)
        filter("response.data", self.modify_response, priority=5)

    def on_disable(self):
        # Unregister hooks when disabled
        hook_manager.unregister("user.created", self.on_user_created)
        hook_manager.remove_filter("response.data", self.modify_response)

    async def on_user_created(self, user):
        """Handle new user creation"""
        await self.create_default_settings(user)

    def modify_response(self, data, request=None):
        """Modify API responses"""
        if isinstance(data, dict):
            data["plugin_version"] = self.version
        return data
```

### Conditional Hooks

```python
from hooks import hook_manager

async def conditional_handler(user):
    """Only run if condition is met"""
    if user.is_premium:
        await send_premium_welcome(user)
    else:
        # Skip for non-premium users
        pass

hook_manager.register("user.created", conditional_handler)
```

### Error Handling in Hooks

```python
from hooks import action
import logging

logger = logging.getLogger(__name__)

@action("user.created")
async def risky_operation(user):
    try:
        # Some operation that might fail
        await external_api.notify(user)
    except Exception as e:
        # Log error but don't stop other hooks
        logger.error(f"Hook failed: {e}")
        # Consider retry logic or dead letter queue
```

## Advanced Features

### Async Hook Execution

```python
from hooks import hook_manager
import asyncio

async def async_handler(data):
    await asyncio.sleep(1)
    print(f"Processed: {data}")

async def sync_handler(data):
    print(f"Sync processed: {data}")

hook_manager.register("process.data", async_handler)
hook_manager.register("process.data", sync_handler)

# Both will be executed
await hook_manager.do_action("process.data", my_data)
```

### Chaining Filters

```python
from hooks import hook_manager

# Each filter receives the output of the previous
hook_manager.add_filter("price", lambda p: p * 1.1)  # Add tax
hook_manager.add_filter("price", lambda p: round(p, 2))  # Round
hook_manager.add_filter("price", lambda p: f"${p}")  # Format

result = await hook_manager.apply_filters("price", 100)
# Result: "$110.00"
```

### Hook Inspection

```python
from hooks import hook_manager

# Check if hook exists
if hook_manager.has_action("user.created"):
    print("User creation hook is registered")

# Get all registered hooks (internal)
for hook_name, handlers in hook_manager._hooks.items():
    print(f"{hook_name}: {len(handlers)} handlers")
```

## Best Practices

### 1. Use Descriptive Hook Names

```python
# Good
db.migrate.before
user.password.changed
email.sent.success

# Bad
before_stuff
user_action
done
```

### 2. Document Hook Arguments

```python
@action("user.created")
async def on_user_created(user):
    """
    Handle new user creation.

    Args:
        user: User model instance with attributes:
            - id: UUID
            - email: str
            - username: str
            - created_at: datetime
    """
    pass
```

### 3. Keep Hooks Fast

```python
# Good - fast operation
@action("request.start")
def log_request(request):
    logger.info(f"Request: {request.method} {request.url}")

# Bad - slow operation
@action("request.start")
async def slow_operation(request):
    await asyncio.sleep(5)  # Don't block requests!
    await process_data()
```

### 4. Handle Hook Failures Gracefully

```python
@action("user.created")
async def send_notification(user):
    try:
        await notification_service.send(user)
    except Exception as e:
        # Don't let hook failure break the flow
        logger.error(f"Notification failed: {e}")
        # Consider retry queue
        await retry_queue.add("notification", user.id)
```

### 5. Unregister Hooks When Done

```python
class TemporaryFeature:
    def __init__(self):
        self.handler = None

    def enable(self):
        self.handler = lambda user: self.process(user)
        hook_manager.register("user.created", self.handler)

    def disable(self):
        if self.handler:
            hook_manager.unregister("user.created", self.handler)
            self.handler = None
```

## Testing Hooks

```python
import pytest
from hooks import hook_manager

@pytest.fixture
def reset_hooks():
    """Reset hooks before each test"""
    hook_manager.remove_all_actions()
    hook_manager.remove_all_filters()
    yield
    hook_manager.remove_all_actions()
    hook_manager.remove_all_filters()

@pytest.mark.asyncio
async def test_action_hook(reset_hooks):
    called_with = []

    async def handler(data):
        called_with.append(data)

    hook_manager.register("test.hook", handler)
    await hook_manager.do_action("test.hook", "test_data")

    assert called_with == ["test_data"]

@pytest.mark.asyncio
async def test_filter_hook(reset_hooks):
    def add_prefix(value):
        return f"prefix_{value}"

    hook_manager.add_filter("test.filter", add_prefix)
    result = await hook_manager.apply_filters("test.filter", "value")

    assert result == "prefix_value"
```

## Troubleshooting

### Common Issues

1. **Hooks not firing**
   - Check hook name spelling
   - Verify handler is registered
   - Confirm `do_action` is being called

2. **Hook execution order wrong**
   - Check priority values (lower = earlier)
   - Verify registration order

3. **Async hooks not working**
   - Use `await hook_manager.do_action()`
   - Mark handlers as `async def`

4. **Memory leaks**
   - Unregister hooks when plugins disable
   - Don't create closures that hold references

## Dependencies

- `asyncio` - Async support
- `typing` - Type hints

## Related Documentation

- [plugins.md](plugins.md) - Plugin lifecycle hooks
- [manager.md](manager.md) - Plugin management
- [xcore.md](xcore.md) - Application lifecycle
