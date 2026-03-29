# Example: Complete Plugin (Email Notification Service)

This example demonstrates a complete, production-grade plugin that integrates with a custom email service, uses Pydantic for validation, and exposes both IPC actions and HTTP routes.

## 1. Plugin Structure

```
plugins/email_notify/
├── plugin.yaml
└── src/
    └── main.py
```

## 2. Manifest (`plugin.yaml`)

```yaml
name: email_notify
version: "2.1.0"
author: "XCore Team"
description: "A complete plugin for sending email notifications."
execution_mode: trusted
entry_point: src/main.py

requires:
  - user_service  # Depends on the user_service plugin

permissions:
  - resource: "ext.email_service"
    actions: ["execute"]
    effect: allow
  - resource: "db.notifications"
    actions: ["read", "write"]
    effect: allow

resources:
  timeout_seconds: 15
  rate_limit:
    calls: 50
    period_seconds: 60
```

## 3. Implementation (`src/main.py`)

```python
from pydantic import BaseModel, EmailStr
from xcore.sdk import TrustedBase, AutoDispatchMixin, RoutedPlugin, action, route, ok, error, validate_payload

# 1. Define Request Schemas
class SendEmailPayload(BaseModel):
    recipient: EmailStr
    subject: str
    body: str

class NotificationLog(BaseModel):
    user_id: int
    message: str

# 2. Plugin Implementation
class Plugin(AutoDispatchMixin, RoutedPlugin, TrustedBase):
    """
    A robust Email Notification plugin with full validation and
    database logging.
    """

    async def on_load(self) -> None:
        # Access external services
        self.email_svc = self.get_service("ext.email_service")
        self.db = self.get_service("db")

        # Subscribe to user creation events
        self.ctx.events.on("user.created", self._on_user_created)
        print("Email Notify Plugin Ready!")

    # --- IPC Actions ---

    @action("send")
    @validate_payload(SendEmailPayload)
    async def send_email_action(self, payload: dict) -> dict:
        """Sends an email and logs it to the database."""
        try:
            # 1. Send via external service
            await self.email_svc.send(
                payload["recipient"],
                payload["subject"],
                payload["body"]
            )

            # 2. Log to database
            async with self.db.session() as session:
                await session.execute(
                    "INSERT INTO logs (recipient, sent_at) VALUES (:r, :t)",
                    {"r": payload["recipient"], "t": "NOW()"}
                )

            return ok(message="Email sent and logged.")

        except Exception as e:
            return error(f"Failed to send email: {str(e)}", code="email_failed")

    # --- HTTP Routes ---

    @route("/status", method="GET", tags=["monitoring"])
    async def get_plugin_status(self):
        """Returns the current status of the email service."""
        health, msg = await self.email_svc.health_check()
        return {
            "service": "email_notify",
            "external_service_ok": health,
            "message": msg
        }

    # --- Event Handlers ---

    async def _on_user_created(self, event):
        """Automatically send a welcome email when a user is created."""
        user_email = event.data.get("email")
        if user_email:
            await self.ctx.plugins.call("email_notify", "send", {
                "recipient": user_email,
                "subject": "Welcome to XCore!",
                "body": "Your account has been successfully created."
            })
```

## 4. Key Takeaways from this Example:

1.  **Multiple Mixins**: We used `AutoDispatchMixin` for IPC and `RoutedPlugin` for HTTP.
2.  **Service Access**: We leveraged `self.get_service()` to interact with both an external extension and the database.
3.  **Validation**: `validate_payload` ensures our IPC calls receive correct data.
4.  **Event Integration**: We subscribed to `user.created` to automate notifications.
5.  **Error Handling**: Standard `ok` and `error` responses maintain consistency across the framework.
