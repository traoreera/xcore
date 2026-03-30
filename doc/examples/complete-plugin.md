# Complete Plugin Example

A full-featured user management plugin demonstrating XCore capabilities.

## Plugin Structure

```
plugins/users/
├── plugin.yaml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── routes.py
│   └── services.py
└── tests/
    └── test_users.py
```

## plugin.yaml

```yaml
name: users
version: 2.0.0
author: XCore Team
description: Complete user management plugin with authentication
execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "ext.email"
    actions: ["send"]
    effect: allow

resources:
  timeout_seconds: 30
  rate_limit:
    calls: 1000
    period_seconds: 60

env:
  JWT_SECRET: "${JWT_SECRET}"
  TOKEN_EXPIRY: "3600"

pagination:
  default_page_size: 20
  max_page_size: 100
```

## models.py

```python
"""Pydantic models for user management."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """Base user model."""
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class UserCreate(UserBase):
    """User creation model."""
    password: str = Field(min_length=8)

    @validator('password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Must contain uppercase')
        if not any(c.islower() for c in v):
            raise ValueError('Must contain lowercase')
        if not any(c.isdigit() for c in v):
            raise ValueError('Must contain digit')
        return v


class UserUpdate(BaseModel):
    """User update model."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class User(UserBase):
    """Full user model with ID."""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """User login model."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PaginatedUsers(BaseModel):
    """Paginated user list."""
    items: list[User]
    total: int
    page: int
    page_size: int
    pages: int
```

## services.py

```python
"""Business logic layer."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt

from .models import UserCreate, UserUpdate


class UserService:
    """User business logic."""

    def __init__(self, db, cache, config):
        self.db = db
        self.cache = cache
        self.config = config
        self.jwt_secret = config.env.get("JWT_SECRET", "secret")
        self.token_expiry = int(config.env.get("TOKEN_EXPIRY", "3600"))

    async def create_user(self, data: UserCreate) -> dict:
        """Create a new user."""
        # Hash password
        password_hash = self._hash_password(data.password)

        # Insert user
        user_id = secrets.token_hex(16)
        now = datetime.utcnow()

        with self.db.session() as session:
            session.execute(
                """
                INSERT INTO users (id, username, email, password_hash, full_name, created_at)
                VALUES (:id, :username, :email, :password_hash, :full_name, :created_at)
                """,
                {
                    "id": user_id,
                    "username": data.username,
                    "email": data.email,
                    "password_hash": password_hash,
                    "full_name": data.full_name,
                    "created_at": now
                }
            )
            session.commit()

        # Invalidate cache
        await self.cache.delete("users:list")

        return {
            "id": user_id,
            "username": data.username,
            "email": data.email,
            "created_at": now.isoformat()
        }

    async def get_user(self, user_id: str) -> Optional[dict]:
        """Get user by ID with caching."""
        cache_key = f"user:{user_id}"

        # Try cache
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Fetch from database
        with self.db.session() as session:
            result = session.execute(
                "SELECT * FROM users WHERE id = :id",
                {"id": user_id}
            )
            user = result.fetchone()

        if user:
            user_dict = dict(user)
            await self.cache.set(cache_key, user_dict, ttl=300)
            return user_dict

        return None

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> dict:
        """List users with pagination."""
        cache_key = f"users:list:{page}:{page_size}:{search or ''}"

        # Try cache
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Build query
        where_clause = ""
        params = {"limit": page_size, "offset": (page - 1) * page_size}

        if search:
            where_clause = "WHERE username ILIKE :search OR email ILIKE :search"
            params["search"] = f"%{search}%"

        with self.db.session() as session:
            # Get total count
            count_result = session.execute(
                f"SELECT COUNT(*) FROM users {where_clause}",
                params
            )
            total = count_result.scalar()

            # Get items
            result = session.execute(
                f"""
                SELECT * FROM users
                {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """,
                params
            )
            items = [dict(row) for row in result.fetchall()]

        response = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size
        }

        # Cache for 60 seconds
        await self.cache.set(cache_key, response, ttl=60)
        return response

    async def update_user(
        self,
        user_id: str,
        data: UserUpdate
    ) -> Optional[dict]:
        """Update user."""
        update_data = data.model_dump(exclude_unset=True)

        if not update_data:
            return await self.get_user(user_id)

        # Build update query
        set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
        update_data["id"] = user_id
        update_data["updated_at"] = datetime.utcnow()
        set_clause += ", updated_at = :updated_at"

        with self.db.session() as session:
            session.execute(
                f"UPDATE users SET {set_clause} WHERE id = :id",
                update_data
            )
            session.commit()

        # Invalidate caches
        await self.cache.delete(f"user:{user_id}")
        await self.cache.delete_pattern("users:list:*")

        return await self.get_user(user_id)

    async def delete_user(self, user_id: str) -> bool:
        """Delete user."""
        with self.db.session() as session:
            result = session.execute(
                "DELETE FROM users WHERE id = :id RETURNING id",
                {"id": user_id}
            )
            deleted = result.fetchone()
            session.commit()

        if deleted:
            await self.cache.delete(f"user:{user_id}")
            await self.cache.delete_pattern("users:list:*")
            return True

        return False

    async def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Authenticate user."""
        with self.db.session() as session:
            result = session.execute(
                "SELECT * FROM users WHERE username = :username",
                {"username": username}
            )
            user = result.fetchone()

        if user and self._verify_password(password, user["password_hash"]):
            return dict(user)

        return None

    def create_token(self, user_id: str) -> str:
        """Create JWT token."""
        expires = datetime.utcnow() + timedelta(seconds=self.token_expiry)
        payload = {
            "sub": user_id,
            "exp": expires,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_token(self, token: str) -> Optional[str]:
        """Verify JWT token and return user_id."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload.get("sub")
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def _hash_password(self, password: str) -> str:
        """Hash password with salt."""
        salt = secrets.token_hex(16)
        hash_value = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000
        )
        return f"{salt}${hash_value.hex()}"

    def _verify_password(self, password: str, hash_string: str) -> bool:
        """Verify password against hash."""
        salt, hash_value = hash_string.split("$")
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000
        )
        return computed.hex() == hash_value
```

## routes.py

```python
"""HTTP routes for user management."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from xcore.sdk import TrustedBase

from .models import (
    PaginatedUsers,
    TokenResponse,
    User,
    UserCreate,
    UserLogin,
    UserUpdate,
)
from .services import UserService


security = HTTPBearer()


def create_router(plugin: TrustedBase, service: UserService) -> APIRouter:
    """Create FastAPI router."""
    router = APIRouter(prefix="/users", tags=["users"])

    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict:
        """Dependency to get current user from token."""
        user_id = service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        user = await service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        return user

    @router.post(
        "/register",
        response_model=User,
        status_code=status.HTTP_201_CREATED
    )
    async def register(data: UserCreate):
        """Register new user."""
        # Check if username exists
        with service.db.session() as session:
            result = session.execute(
                "SELECT id FROM users WHERE username = :username",
                {"username": data.username}
            )
            if result.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )

        user = await service.create_user(data)
        return user

    @router.post("/login", response_model=TokenResponse)
    async def login(data: UserLogin):
        """Login user."""
        user = await service.authenticate(data.username, data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        token = service.create_token(user["id"])
        return TokenResponse(
            access_token=token,
            expires_in=service.token_expiry
        )

    @router.get("/me", response_model=User)
    async def get_me(current_user: dict = Depends(get_current_user)):
        """Get current user."""
        return current_user

    @router.get("/", response_model=PaginatedUsers)
    async def list_users(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        search: str | None = None,
        current_user: dict = Depends(get_current_user)
    ):
        """List users."""
        return await service.list_users(page, page_size, search)

    @router.get("/{user_id}", response_model=User)
    async def get_user(
        user_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get user by ID."""
        user = await service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    @router.put("/{user_id}", response_model=User)
    async def update_user(
        user_id: str,
        data: UserUpdate,
        current_user: dict = Depends(get_current_user)
    ):
        """Update user."""
        # Only allow self-update or admin
        if current_user["id"] != user_id and not current_user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )

        user = await service.update_user(user_id, data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    @router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_user(
        user_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Delete user."""
        # Only allow self-delete or admin
        if current_user["id"] != user_id and not current_user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )

        deleted = await service.delete_user(user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

    return router
```

## main.py

```python
"""Main plugin module."""
from xcore.sdk import TrustedBase, error, ok

from .routes import create_router
from .services import UserService


class Plugin(TrustedBase):
    """User management plugin."""

    async def on_load(self) -> None:
        """Initialize plugin."""
        # Get services
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

        # Initialize user service
        self.user_service = UserService(
            self.db,
            self.cache,
            self.ctx.config
        )

        print("✅ Users plugin loaded")

    def get_router(self):
        """Return FastAPI router."""
        return create_router(self, self.user_service)

    async def handle(self, action: str, payload: dict) -> dict:
        """Handle IPC actions."""
        try:
            if action == "create":
                from .models import UserCreate
                data = UserCreate(**payload)
                user = await self.user_service.create_user(data)
                return ok(user=user)

            if action == "get":
                user = await self.user_service.get_user(payload["user_id"])
                if user:
                    return ok(user=user)
                return error("User not found", code="not_found")

            if action == "list":
                result = await self.user_service.list_users(
                    page=payload.get("page", 1),
                    page_size=payload.get("page_size", 20)
                )
                return ok(**result)

            if action == "authenticate":
                user = await self.user_service.authenticate(
                    payload["username"],
                    payload["password"]
                )
                if user:
                    token = self.user_service.create_token(user["id"])
                    return ok(user=user, token=token)
                return error("Invalid credentials", code="auth_failed")

            if action == "verify_token":
                user_id = self.user_service.verify_token(payload["token"])
                if user_id:
                    user = await self.user_service.get_user(user_id)
                    return ok(valid=True, user=user)
                return ok(valid=False)

            return error(f"Unknown action: {action}", code="unknown_action")

        except Exception as e:
            return error(str(e), code="internal_error")
```

## Migration

```sql
-- migrations/001_create_users.sql
CREATE TABLE users (
    id VARCHAR(32) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created ON users(created_at DESC);
```

## Usage Examples

### HTTP API

```bash
# Register
curl -X POST http://localhost:8082/plugins/users/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password": "SecurePass123",
    "full_name": "Alice Smith"
  }'

# Login
curl -X POST http://localhost:8082/plugins/users/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "SecurePass123"
  }'

# Get current user
curl http://localhost:8082/plugins/users/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"

# List users
curl "http://localhost:8082/plugins/users/users/?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### IPC

```python
# From another plugin
result = await self.ctx.plugins.call(
    "users",
    "authenticate",
    {"username": "alice", "password": "pass"}
)

result = await self.ctx.plugins.call(
    "users",
    "verify_token",
    {"token": "jwt_token_here"}
)
```

## Summary

This complete example demonstrates:

- ✅ Clean architecture (models, services, routes)
- ✅ Pydantic validation
- ✅ Database with SQL
- ✅ Caching layer
- ✅ Authentication & authorization
- ✅ Pagination
- ✅ Error handling
- ✅ Both HTTP and IPC APIs
