# Security Best Practices

Security guidelines for developing XCore plugins and deployments.

## Overview

XCore provides multiple security layers:

1. **Sandboxing** — Isolated execution for untrusted code
2. **AST Scanning** — Static analysis of plugin code
3. **Signature Verification** — HMAC-based plugin signing
4. **Permission System** — Resource-based access control
5. **Rate Limiting** — Per-plugin call limits

## Plugin Security Modes

### Trusted Mode

**When to use**: Internal plugins, well-reviewed code

```yaml
name: internal_plugin
execution_mode: trusted
```

Characteristics:
- Runs in main process
- Full service access
- Optional code signing
- Best performance

### Sandboxed Mode

**When to use**: Third-party plugins, untrusted code

```yaml
name: external_plugin
execution_mode: sandboxed
```

Characteristics:
- Runs in isolated subprocess
- AST validation
- Resource limits
- IPC communication

## Secure Plugin Development

### 1. Input Validation

Always validate inputs using Pydantic:

```python
from pydantic import BaseModel, EmailStr, Field, validator
from xcore.sdk import TrustedBase, ok, error


class CreateUserInput(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    age: int = Field(ge=0, le=150)
    password: str = Field(min_length=8)

    @validator('password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v


class Plugin(TrustedBase):

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "create_user":
            try:
                # Validate input
                validated = CreateUserInput(**payload)

                # Process validated data
                await self._create_user(validated)

                return ok(user_id="123")

            except ValueError as e:
                return error(str(e), code="validation_error")

        return ok()
```

### 2. SQL Injection Prevention

Use parameterized queries:

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.db = self.get_service("db")

    async def get_user(self, user_id: str) -> dict:
        # ❌ NEVER do this
        # query = f"SELECT * FROM users WHERE id = '{user_id}'"

        # ✅ Use parameterized queries
        with self.db.session() as session:
            result = session.execute(
                "SELECT * FROM users WHERE id = :id",
                {"id": user_id}
            )
            return result.fetchone()
```

### 3. Authentication & Authorization

Implement proper auth in your plugins:

```python
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from xcore.sdk import TrustedBase
import jwt


class Plugin(TrustedBase):

    security = HTTPBearer()

    def get_router(self) -> APIRouter:
        router = APIRouter()

        async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(self.security)):
            try:
                payload = jwt.decode(
                    credentials.credentials,
                    self.ctx.config.app.secret_key,
                    algorithms=["HS256"]
                )
                return payload
            except jwt.ExpiredSignatureError:
                raise HTTPException(401, "Token expired")
            except jwt.InvalidTokenError:
                raise HTTPException(401, "Invalid token")

        @router.get("/admin/data")
        async def admin_data(user=Depends(verify_token)):
            # Check admin role
            if user.get("role") != "admin":
                raise HTTPException(403, "Admin access required")

            return {"data": "sensitive"}

        return router
```

### 4. Secrets Management

Never hardcode secrets:

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # ✅ Get from environment
        self.api_key = self.ctx.env.get("EXTERNAL_API_KEY")

        if not self.api_key:
            raise RuntimeError("EXTERNAL_API_KEY not set")

    async def call_external_api(self, data: dict):
        # Use the API key securely
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # ... make request
```

### 5. File System Security

Restrict file access:

```yaml
# plugin.yaml
filesystem:
  allowed_paths: ["data/", "uploads/"]
  denied_paths: ["src/", "../", "/etc/"]
```

```python
import os
from pathlib import Path


class Plugin(TrustedBase):

    async def save_upload(self, filename: str, content: bytes) -> dict:
        # ✅ Validate path
        base_path = Path(self.ctx.config.plugin_dir) / "uploads"
        target_path = (base_path / filename).resolve()

        # Ensure path is within allowed directory
        if not str(target_path).startswith(str(base_path)):
            raise ValueError("Invalid path")

        # ✅ Check extension
        allowed_extensions = {".txt", ".pdf", ".jpg"}
        if target_path.suffix not in allowed_extensions:
            raise ValueError("File type not allowed")

        # ✅ Write safely
        target_path.write_bytes(content)

        return ok(path=str(target_path))
```

### 6. Rate Limiting

Set appropriate limits:

```yaml
# plugin.yaml
resources:
  rate_limit:
    calls: 100           # requests per period
    period_seconds: 60   # time window
```

Implement custom rate limiting:

```python
from xcore.sdk import TrustedBase
import time


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")

    async def handle(self, action: str, payload: dict) -> dict:
        user_id = payload.get("user_id")
        key = f"rate_limit:{user_id}:{action}"

        # Check custom rate limit
        current = await self.cache.get(key) or 0
        if current >= 10:  # 10 per minute per user
            return error("Rate limit exceeded", code="rate_limit")

        # Increment counter
        await self.cache.set(key, current + 1, ttl=60)

        # Process action
        return ok()
```

### 7. Secure Communication

Use HTTPS in production:

```yaml
# production.yaml
app:
  env: production
  debug: false
```

```python
class Plugin(TrustedBase):

    async def make_request(self, url: str):
        import httpx

        # ✅ Use HTTPS
        if not url.startswith("https://"):
            raise ValueError("HTTPS required")

        # ✅ Verify SSL certificates
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(url)
            return response
```

## Deployment Security

### Production Configuration

```yaml
# production.yaml
app:
  env: production
  debug: false
  secret_key: ${APP_SECRET_KEY}  # Use strong secret

plugins:
  strict_trusted: true           # Require signatures
  interval: 0                   # Disable hot reload

security:
  allowed_imports:              # Restrict imports
    - json
    - re
    - datetime
    # ...

  forbidden_imports:            # Explicitly forbid
    - os
    - sys
    - subprocess
    - eval
    - exec
```

### Environment Variables

Store sensitive data in environment:

```bash
# .env
APP_SECRET_KEY=$(openssl rand -hex 32)
PLUGIN_SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
```

### Reverse Proxy Setup

Use Nginx as reverse proxy:

```nginx
# /etc/nginx/sites-available/xcore
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Sandboxing Guide

### Setting Up Sandboxed Plugins

```yaml
name: untrusted_plugin
execution_mode: sandboxed

permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "db.*"
    actions: ["read"]
    effect: allow
  - resource: "scheduler"
    actions: ["*"]
    effect: deny

resources:
  timeout_seconds: 30
  max_memory_mb: 256
  max_disk_mb: 100
  rate_limit:
    calls: 50
    period_seconds: 60

filesystem:
  allowed_paths: ["data/"]
  denied_paths: ["src/", "../"]
```

### AST Validation

Forbidden imports in sandboxed mode:

```python
# These will be rejected
import os           # ❌ File system access
import sys          # ❌ System access
import subprocess   # ❌ Command execution
import socket       # ❌ Network access
import eval         # ❌ Code execution
import exec         # ❌ Code execution
import pickle       # ❌ Arbitrary code execution
```

### Testing Sandboxed Plugins

```python
# Test that sandbox restrictions work
async def test_sandbox():
    # This should fail for sandboxed plugins
    result = await supervisor.call(
        "sandboxed_plugin",
        "attempt_os_access",
        {}
    )
    assert result["status"] == "error"
```

## Plugin Signing

### Generate Signing Key

```bash
# Generate secure key
PLUGIN_SECRET_KEY=$(openssl rand -hex 32)
echo "PLUGIN_SECRET_KEY=$PLUGIN_SECRET_KEY" >> .env
```

### Sign a Plugin

```bash
# Using CLI
xcore plugin sign ./plugins/my_plugin --key $PLUGIN_SECRET_KEY

# Or manually
python -c "
from xcore.kernel.security.signature import sign_plugin
sign_plugin('./plugins/my_plugin', key='your-secret-key')
"
```

### Verify Signature

```bash
# Using CLI
xcore plugin verify ./plugins/my_plugin --key $PLUGIN_SECRET_KEY

# Or programmatically
from xcore.kernel.security.signature import verify_plugin
valid = verify_plugin('./plugins/my_plugin', key='your-secret-key')
print(f"Signature valid: {valid}")
```

## Security Checklist

### Plugin Development

- [ ] Input validation using Pydantic
- [ ] Parameterized SQL queries
- [ ] Proper authentication/authorization
- [ ] Secrets in environment variables
- [ ] File path validation
- [ ] Rate limiting configured
- [ ] HTTPS for external calls
- [ ] No hardcoded credentials
- [ ] Error messages don't leak information
- [ ] Logging of security events

### Production Deployment

- [ ] Debug mode disabled
- [ ] Strong secret keys
- [ ] Plugin signing enabled
- [ ] Sandboxing for untrusted plugins
- [ ] HTTPS enabled
- [ ] Rate limiting configured
- [ ] Resource limits set
- [ ] Hot reload disabled
- [ ] Monitoring and alerting
- [ ] Regular security updates

## Incident Response

### Detecting Security Issues

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Log security events
        self.ctx.events.on("security.suspicious", self._on_suspicious)

    async def handle(self, action: str, payload: dict) -> dict:
        # Log failed auth attempts
        if action == "login":
            success = await self._authenticate(payload)
            if not success:
                await self.ctx.events.emit("security.failed_login", {
                    "ip": payload.get("client_ip"),
                    "username": payload.get("username"),
                    "timestamp": time.time()
                })
                return error("Authentication failed")

        return ok()

    async def _on_suspicious(self, event):
        """Handle suspicious activity."""
        # Alert administrators
        # Block IP if necessary
        # Log to security system
        pass
```

### Emergency Shutdown

```python
# Emergency plugin to handle security incidents
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.ctx.events.on("security.emergency", self._emergency_shutdown)

    async def _emergency_shutdown(self, event):
        """Emergency shutdown handler."""
        reason = event.data.get("reason")

        # Log emergency
        self.ctx.logger.critical(f"EMERGENCY SHUTDOWN: {reason}")

        # Disable all non-essential plugins
        for plugin in self.ctx.registry.list():
            if plugin not in ["emergency", "logging"]:
                await self.ctx.plugins.unload(plugin)

        # Alert on-call
        await self._alert_oncall(reason)
```

## Next Steps

- [Testing Security](testing-security.md)
- [Audit Logging](audit-logging.md)
- [Compliance Guide](compliance.md)
