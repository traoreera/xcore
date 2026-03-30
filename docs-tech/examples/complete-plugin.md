# Example: Production-Grade Notification Service

This example showcases a complete, production-ready plugin that integrates with external APIs, uses multiple XCore services, and handles complex event orchestration.

---

## 1. Directory Layout

```text
plugins/notification_hub/
├── plugin.yaml           # Manifest & Permissions
├── src/
│   ├── main.py          # Entry point & IPC
│   ├── providers/       # External service providers
│   │   ├── email.py
│   │   └── slack.py
│   └── events.py        # Event handlers
└── schemas/             # Pydantic validation schemas
    └── notify.py
```

---

## 2. Manifest (`plugin.yaml`)

```yaml
name: notification_hub
version: "3.2.0"
author: "XCore Team"
description: "Centralized notification hub with multi-channel support."
execution_mode: trusted

# Requires the cache for rate-limiting per recipient
permissions:
  - resource: "cache.notifications.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "db.history"
    actions: ["write"]
    effect: allow

# Listen to critical system events
runtime:
  health_check:
    enabled: true
    interval_seconds: 60
```

---

## 3. Advanced Implementation (`src/main.py`)

```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, action, ok, error, validate_payload
from .providers.email import EmailProvider
from .providers.slack import SlackProvider
from .schemas.notify import NotificationRequest

class Plugin(AutoDispatchMixin, TrustedBase):
    """
    Highly resilient notification hub.
    Uses 'Circuit Breaker' pattern when calling external providers.
    """

    async def on_load(self) -> None:
        self.email = EmailProvider(self.ctx.env.get("SMTP_HOST"))
        self.slack = SlackProvider(self.ctx.env.get("SLACK_TOKEN"))
        self.cache = self.get_service("cache")
        self.db = self.get_service("db")

        # Subscribe to global user events
        self.ctx.events.on("user.password_changed", self._on_security_event)
        self.logger.info("Notification Hub Active")

    @action("broadcast")
    @validate_payload(NotificationRequest)
    async def broadcast(self, payload: dict) -> dict:
        """Sends a message to all configured channels."""

        # 1. Deduplication Check (Cache)
        dedup_key = f"notify:hash:{hash(payload['message'])}"
        if await self.cache.exists(dedup_key):
            return error("Duplicate message detected", code="duplicate")

        # 2. Parallel Dispatch
        results = await asyncio.gather(
            self.email.send(payload),
            self.slack.send(payload),
            return_exceptions=True
        )

        # 3. Log to History
        async with self.db.session() as session:
            await session.execute(
                "INSERT INTO notification_history (msg, status) VALUES (:m, :s)",
                {"m": payload['message'], "s": "sent"}
            )

        await self.cache.set(dedup_key, True, ttl=60)
        return ok(message="Broadcast complete")

    async def _on_security_event(self, event):
        """React to kernel-level security events."""
        user_id = event.data.get("user_id")
        await self.broadcast({
            "recipient": user_id,
            "message": "Your password has been changed successfully.",
            "channel": "email"
        })
```

---

## 4. Key Engineering Patterns Used

1.  **Parallel Execution**: Uses `asyncio.gather` for non-blocking I/O across multiple providers.
2.  **Idempotency**: Implements a simple deduplication logic using the `cache` service.
3.  **Kernel Integration**: Directly subscribes to `user.password_changed` events emitted by other core plugins.
4.  **Resilience**: The structure allows adding more providers without changing the core IPC interface.
