# middleware - Custom Middleware Module

## Overview

The `middleware` module provides custom FastAPI middleware for request/response processing. The main component is the access control middleware that enforces role-based and permission-based access rules.

## Module Structure

```
middleware/
└── access_control_Middleware.py    # JWT validation, role/permission checking
```

## Core Components

### AccessControlMiddleware

Middleware for controlling access to routes based on JWT tokens, roles, and permissions.

```python
class AccessControlMiddleware(BaseHTTPMiddleware):
    """
    Middleware for access control based on:
    - JWT token validation
    - Role-based access control (RBAC)
    - Permission-based access control
    - Public route exemptions
    """

    def __init__(
        self,
        app: ASGIApp,
        rules: List[AccessRule] = None,
        default_authenticated: bool = False
    ):
        """
        Initialize middleware.

        Args:
            app: ASGI application
            rules: List of access rules
            default_authenticated: Require auth by default
        """
```

## Access Rules

### AccessRule Model

```python
class AccessRule:
    """Single access control rule"""

    def __init__(
        self,
        path: str,                      # URL path pattern (supports wildcards)
        methods: List[str] = None,      # HTTP methods (None = all)
        roles: List[str] = None,        # Required roles
        permissions: List[str] = None,  # Required permissions
        public: bool = False            # Public access (skip auth)
    ):
        self.path = path
        self.methods = methods or ["*"]
        self.roles = roles or []
        self.permissions = permissions or []
        self.public = public
```

### Rule Matching

Rules are matched in order, first match wins:

```python
# Public routes (no auth required)
AccessRule(path="/auth/login", methods=["POST"], public=True)
AccessRule(path="/auth/register", methods=["POST"], public=True)
AccessRule(path="/static/*", public=True)

# Role-based routes
AccessRule(path="/admin/*", roles=["admin"])
AccessRule(path="/manager/*", roles=["admin", "manager"])

# Permission-based routes
AccessRule(
    path="/api/users/*",
    permissions=["users:read", "users:write"]
)

# Mixed routes
AccessRule(
    path="/api/content/*",
    roles=["editor", "admin"],
    permissions=["content:write"]
)
```

## Usage

### Basic Setup

```python
from fastapi import FastAPI
from middleware.access_control_Middleware import AccessControlMiddleware
from configurations import Xcorecfg

app = FastAPI()
config = Xcorecfg.from_file("config.json")

# Add middleware
app.add_middleware(
    AccessControlMiddleware,
    rules=config.middleware.access_rules,
    default_authenticated=config.middleware.default_authenticated
)
```

### Configuration

```json
{
  "middleware": {
    "enabled": true,
    "access_rules": [
      {
        "path": "/health",
        "methods": ["GET"],
        "public": true
      },
      {
        "path": "/auth/*",
        "methods": ["POST"],
        "public": true
      },
      {
        "path": "/auth/me",
        "methods": ["GET"],
        "public": false
      },
      {
        "path": "/admin/*",
        "roles": ["admin"]
      },
      {
        "path": "/manager/plugins/*",
        "roles": ["admin", "manager"],
        "permissions": ["plugins:manage"]
      },
      {
        "path": "/api/*",
        "roles": ["user", "admin"]
      }
    ],
    "default_authenticated": false
  }
}
```

### Path Patterns

The middleware supports glob-style patterns:

| Pattern | Matches |
|---------|---------|
| `/auth/login` | Exact match |
| `/auth/*` | `/auth/login`, `/auth/register`, etc. |
| `/api/**` | `/api/users`, `/api/users/123`, etc. |
| `*/admin/*` | Any path containing `/admin/` |

## How It Works

### Request Flow

```
1. Request arrives
2. Match path against rules
3. If public → allow
4. Extract JWT token from header
5. Validate token
6. Extract user info (roles, permissions)
7. Check against rule requirements
8. Allow or deny request
```

### Token Extraction

```python
# From Authorization header
Authorization: Bearer <jwt_token>

# Token is extracted and validated
# User info is attached to request.state.user
```

### Response Handling

```python
# Success - request continues
if authorized:
    request.state.user = user
    return await call_next(request)

# Failure - return error response
if not token:
    return JSONResponse(
        status_code=401,
        content={"detail": "Authentication required"}
    )

if not has_roles:
    return JSONResponse(
        status_code=403,
        content={"detail": "Insufficient roles"}
    )
```

## Advanced Usage

### Custom Error Handler

```python
from middleware.access_control_Middleware import AccessControlMiddleware

class CustomAccessMiddleware(AccessControlMiddleware):
    async def handle_auth_error(self, request: Request, error: str) -> Response:
        """Custom error response"""
        return JSONResponse(
            status_code=401,
            content={
                "error": "Authentication failed",
                "message": error,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

app.add_middleware(CustomAccessMiddleware, rules=rules)
```

### Programmatic Rule Creation

```python
from middleware.access_control_Middleware import AccessRule

rules = [
    # Public health check
    AccessRule(path="/health", methods=["GET"], public=True),

    # Auth endpoints (some public)
    AccessRule(path="/auth/login", methods=["POST"], public=True),
    AccessRule(path="/auth/register", methods=["POST"], public=True),

    # All other auth endpoints require authentication
    AccessRule(path="/auth/*"),

    # Admin only
    AccessRule(path="/admin/*", roles=["admin"]),

    # Manager endpoints
    AccessRule(
        path="/manager/*",
        roles=["admin", "manager"]
    ),

    # API endpoints (any authenticated user)
    AccessRule(path="/api/*", roles=["user", "admin", "manager"]),

    # Everything else (default)
    AccessRule(path="*", public=True)  # Or require auth
]
```

### Skipping Middleware for Specific Routes

```python
# In your route
@app.get("/public-info")
async def public_info(request: Request):
    # This route is public via access rule
    return {"info": "Public data"}

# Or use dependency
from fastapi import Depends

async def no_auth(request: Request):
    request.state.skip_auth = True

@app.get("/special", dependencies=[Depends(no_auth)])
async def special_route():
    return {"data": "special"}
```

## Integration with Auth Module

The middleware uses the `auth` module for token validation:

```python
from auth.dependencies import get_current_user_from_token

class AccessControlMiddleware:
    async def authenticate(self, token: str) -> User:
        """Validate token and return user"""
        return await get_current_user_from_token(token)
```

## Testing

### Unit Testing

```python
from fastapi.testclient import TestClient
from middleware.access_control_Middleware import AccessControlMiddleware

def test_public_route():
    app = FastAPI()
    app.add_middleware(
        AccessControlMiddleware,
        rules=[AccessRule(path="/public", public=True)]
    )

    @app.get("/public")
    async def public():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/public")
    assert response.status_code == 200

def test_protected_route():
    app = FastAPI()
    app.add_middleware(
        AccessControlMiddleware,
        rules=[AccessRule(path="/protected", roles=["user"])]
    )

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    client = TestClient(app)

    # Without token
    response = client.get("/protected")
    assert response.status_code == 401

    # With valid token
    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code == 200
```

## Troubleshooting

### Common Issues

1. **Token not recognized**
   - Check `Authorization` header format
   - Verify JWT secret key configuration

2. **Roles not working**
   - Ensure user has roles assigned in database
   - Check role names match exactly (case-sensitive)

3. **Rules not matching**
   - Check rule order (first match wins)
   - Verify path patterns are correct

4. **Performance issues**
   - Reduce number of rules
   - Use more specific patterns
   - Enable caching for user lookups

### Debug Mode

```python
# Enable debug logging
import logging
logging.getLogger("middleware.access_control").setLevel(logging.DEBUG)

# Or in config
{
  "middleware": {
    "debug": true
  }
}
```

## Dependencies

- `fastapi` - Web framework
- `auth` - Authentication module
- `admin` - Role/permission checking
- `starlette` - Base middleware classes

## Related Documentation

- [auth.md](auth.md) - Authentication module
- [admin.md](admin.md) - Role and permission management
- [configurations.md](configurations.md) - Middleware configuration
