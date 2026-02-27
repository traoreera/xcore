# Event System

XCore provides a powerful event bus for inter-plugin communication and system-wide event handling.

## Overview

The `EventBus` allows:
- **Publish/subscribe** pattern for decoupled communication
- **Prioritized** event handlers
- **One-time** subscriptions
- **Synchronous** and **asynchronous** handlers
- **Event propagation** control

## Basic Usage

### Subscribing to Events

```python
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        """Subscribe to events during plugin load."""
        # Subscribe to user creation events
        self.ctx.events.on("user.created", self._on_user_created)

        # Subscribe with priority (higher = earlier)
        self.ctx.events.on("order.placed", self._validate_order, priority=100)
        self.ctx.events.on("order.placed", self._send_confirmation, priority=50)

        # One-time subscription
        self.ctx.events.once("system.ready", self._on_system_ready)

    async def _on_user_created(self, event):
        """Handle user creation."""
        user_id = event.data.get("user_id")
        email = event.data.get("email")

        print(f"User {user_id} created with email {email}")

        # Could send welcome email here

    async def _validate_order(self, event):
        """Validate order (runs first due to high priority)."""
        order_id = event.data.get("order_id")

        # Validation logic
        is_valid = await self._check_inventory(order_id)

        if not is_valid:
            # Stop propagation to other handlers
            event.stop()
            print(f"Order {order_id} validation failed")

    async def _send_confirmation(self, event):
        """Send order confirmation email."""
        order_id = event.data.get("order_id")
        user_email = event.data.get("email")

        print(f"Sending confirmation for order {order_id} to {user_email}")

    async def _on_system_ready(self, event):
        """Handle system ready (runs once)."""
        print("System is ready!")
        # Initialize plugin resources

    async def on_unload(self) -> None:
        """Clean up subscriptions."""
        # Unsubscribe from events
        self.ctx.events.unsubscribe("user.created", self._on_user_created)
```

### Emitting Events

```python
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.post("/users")
        async def create_user(data: dict):
            """Create user and emit event."""
            # Create user logic
            user_id = await self._create_user_in_db(data)

            # Emit event
            await self.ctx.events.emit("user.created", {
                "user_id": user_id,
                "username": data["username"],
                "email": data["email"],
                "timestamp": datetime.now().isoformat()
            })

            return {"id": user_id}

        @router.post("/orders")
        async def place_order(data: dict):
            """Place order and emit event."""
            order_id = await self._create_order(data)

            # Emit with source information
            await self.ctx.events.emit(
                "order.placed",
                {
                    "order_id": order_id,
                    "user_id": data["user_id"],
                    "amount": data["amount"],
                    "items": data["items"]
                },
                source="order_plugin"
            )

            return {"order_id": order_id}

        return router

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "process":
            # Process something
            result = await self._process(payload)

            # Fire-and-forget event from synchronous code
            self.ctx.events.emit_sync("process.completed", {
                "action_id": payload.get("id"),
                "result": result
            })

            return {"status": "ok"}

        return {"status": "ok"}
```

## Event Object

The event object passed to handlers:

```python
@dataclass
class Event:
    name: str           # Event name
    data: dict          # Event data/payload
    source: str | None  # Event source
    propagate: bool     # Whether to continue to other handlers
    cancelled: bool     # Whether event is cancelled

    def stop(self) -> None:
        """Stop propagation to other handlers."""
        self.propagate = False

    def cancel(self) -> None:
        """Cancel the event entirely."""
        self.cancelled = True
```

## Event Patterns

### Request/Response Pattern

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Subscribe to requests
        self.ctx.events.on("payment.request", self._process_payment)

    async def _process_payment(self, event):
        """Process payment request."""
        request_id = event.data.get("request_id")
        amount = event.data.get("amount")
        currency = event.data.get("currency")

        try:
            # Process payment
            result = await self._charge_card(amount, currency)

            # Emit response
            await self.ctx.events.emit("payment.response", {
                "request_id": request_id,
                "status": "success",
                "transaction_id": result["id"]
            })
        except Exception as e:
            await self.ctx.events.emit("payment.response", {
                "request_id": request_id,
                "status": "failed",
                "error": str(e)
            })

    # Another plugin can listen for responses
    async def wait_for_payment(self, request_id: str):
        """Wait for payment response."""
        response = None

        @self.ctx.events.once("payment.response")
        async def on_response(event):
            if event.data.get("request_id") == request_id:
                nonlocal response
                response = event.data

        # Wait for response (with timeout)
        for _ in range(30):  # 30 seconds timeout
            await asyncio.sleep(1)
            if response:
                return response

        return {"status": "timeout"}
```

### Event Chaining

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Chain of events
        self.ctx.events.on("user.registered", self._on_user_registered)
        self.ctx.events.on("profile.created", self._on_profile_created)
        self.ctx.events.on("welcome.sent", self._on_welcome_sent)

    async def _on_user_registered(self, event):
        """Create profile after user registration."""
        user_id = event.data["user_id"]

        # Create profile
        profile = await self._create_profile(user_id)

        # Emit next event in chain
        await self.ctx.events.emit("profile.created", {
            "user_id": user_id,
            "profile_id": profile["id"]
        })

    async def _on_profile_created(self, event):
        """Send welcome email after profile creation."""
        user_id = event.data["user_id"]
        user = await self._get_user(user_id)

        # Send email
        await self._send_welcome_email(user["email"])

        await self.ctx.events.emit("welcome.sent", {
            "user_id": user_id,
            "email": user["email"]
        })

    async def _on_welcome_sent(self, event):
        """Log completion."""
        print(f"Onboarding complete for user {event.data['user_id']}")
```

### Conditional Handling

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Only handle events for premium users
        self.ctx.events.on("order.placed", self._handle_premium_order)

    async def _handle_premium_order(self, event):
        """Handle order only for premium users."""
        user_id = event.data.get("user_id")

        # Check if user is premium
        is_premium = await self._is_premium_user(user_id)

        if not is_premium:
            # Skip this event
            return

        # Apply premium benefits
        await self._apply_discount(event.data["order_id"], percentage=10)
        await self._add_priority_shipping(event.data["order_id"])
```

### Event Broadcasting

```python
class Plugin(TrustedBase):

    async def notify_all(self, message: str):
        """Broadcast notification to all listeners."""
        await self.ctx.events.emit("notification.broadcast", {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "priority": "high"
        })

    # Multiple plugins can listen:
    # - Email plugin sends email
    # - Push notification plugin sends push
    # - Logging plugin logs the notification
    # - Analytics plugin tracks metrics
```

## System Events

XCore emits system events:

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # System startup
        self.ctx.events.on("xcore.booted", self._on_system_boot)

        # Plugin lifecycle
        self.ctx.events.on("xcore.plugins.loaded", self._on_plugins_loaded)
        self.ctx.events.on("plugin.*.reloaded", self._on_plugin_reloaded)

        # Service events
        self.ctx.events.on("service.error", self._on_service_error)

    async def _on_system_boot(self, event):
        """System has finished booting."""
        print("XCore system is ready!")

    async def _on_plugins_loaded(self, event):
        """All plugins have been loaded."""
        report = event.data.get("report", {})
        loaded = len(report.get("loaded", []))
        print(f"{loaded} plugins loaded successfully")

    async def _on_plugin_reloaded(self, event):
        """A plugin was reloaded."""
        # Event name pattern: plugin.{name}.reloaded
        print(f"Plugin event: {event.name}")

    async def _on_service_error(self, event):
        """Service error occurred."""
        service_name = event.data.get("service")
        error_msg = event.data.get("error")
        print(f"Service {service_name} error: {error_msg}")
```

## Handler Registration Patterns

### Decorator Style

```python
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Register using decorators
        events = self.ctx.events

        @events.on("user.created", priority=50)
        async def send_welcome(event):
            await self._send_email(event.data["email"])

        @events.on("order.placed", priority=100)
        async def validate(event):
            if not await self._check_stock(event.data["items"]):
                event.stop()

        # Keep references to unregister later
        self._handlers = [send_welcome, validate]

    async def on_unload(self) -> None:
        # Clean up handlers
        for handler in getattr(self, "_handlers", []):
            self.ctx.events.unsubscribe("user.created", handler)
```

### Class-based Handlers

```python
class EventHandlers:
    """Separate event handlers for organization."""

    def __init__(self, plugin):
        self.plugin = plugin

    async def on_user_created(self, event):
        await self.plugin._send_welcome(event.data)

    async def on_order_placed(self, event):
        await self.plugin._process_order(event.data)


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.handlers = EventHandlers(self)

        self.ctx.events.on("user.created", self.handlers.on_user_created)
        self.ctx.events.on("order.placed", self.handlers.on_order_placed)
```

## Best Practices

1. **Always clean up**: Unsubscribe in `on_unload()`
2. **Use priorities**: Control execution order
3. **Handle errors**: Wrap handler logic in try/except
4. **Keep handlers fast**: For long operations, delegate to background tasks
5. **Document events**: Maintain an event catalog

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        """Set up event handlers."""
        events = self.ctx.events

        # High priority: validation
        events.on("order.placed", self._validate_order, priority=100)

        # Medium priority: processing
        events.on("order.placed", self._process_order, priority=50)

        # Low priority: notifications
        events.on("order.placed", self._notify_user, priority=10)

    async def _validate_order(self, event):
        """Validate order before processing."""
        try:
            is_valid = await self._check_order_valid(event.data)
            if not is_valid:
                event.stop()
                await self._log_invalid_order(event.data)
        except Exception as e:
            # Log but don't stop other handlers
            print(f"Validation error: {e}")

    async def _process_order(self, event):
        """Process validated order."""
        try:
            # Delegate to background task
            await self._schedule_order_processing(event.data)
        except Exception as e:
            await self.ctx.events.emit("order.processing_failed", {
                "order_id": event.data["order_id"],
                "error": str(e)
            })

    async def on_unload(self) -> None:
        """Clean up event handlers."""
        self.ctx.events.clear("order.placed")
```

## Event Catalog Template

Document your events:

```markdown
## Event Catalog

### user.created
- **Description**: Emitted when a new user is registered
- **Data**: {user_id, username, email, timestamp}
- **Source**: auth_plugin
- **Consumers**: email_plugin, analytics_plugin

### order.placed
- **Description**: Emitted when an order is placed
- **Data**: {order_id, user_id, amount, items}
- **Source**: order_plugin
- **Consumers**: payment_plugin, inventory_plugin, notification_plugin

### payment.completed
- **Description**: Emitted when payment is successful
- **Data**: {order_id, transaction_id, amount}
- **Source**: payment_plugin
- **Consumers**: order_plugin, email_plugin
```

## Next Steps

- [Security Best Practices](security.md)
- [Testing Plugins](testing.md)
- [Advanced Patterns](advanced-patterns.md)
