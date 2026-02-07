# auth - Authentication & User Management Module

## Overview

The `auth` module provides JWT-based authentication with user management and role assignment. It handles user registration, login, token generation, and current user retrieval.

## Module Structure

```
auth/
├── __init__.py          # Module initialization
├── models.py            # User SQLAlchemy models
├── schemas.py           # Pydantic schemas
├── routes.py            # API endpoints
├── service.py           # Business logic
├── dependencies.py      # FastAPI dependencies
└── init_root.py         # Root user initialization
```

## Core Components

### Models (`models.py`)

#### `User`

SQLAlchemy model for user accounts.

```python
class User(Base):
    """User account model"""

    __tablename__ = "users"

    id: UUID                    # Unique user ID
    email: str                  # User email (unique)
    username: str               # Username (unique)
    hashed_password: str        # Bcrypt hashed password
    is_active: bool             # Account status
    is_superuser: bool          # Superuser flag
    roles: List[Role]           # Associated roles
    created_at: datetime        # Creation timestamp
    updated_at: datetime        # Last update timestamp
    last_login: datetime        # Last login timestamp
```

**Relationships:**
- `roles` - Many-to-many relationship with Role model (from `admin` module)

### Schemas (`schemas.py`)

#### `UserCreate`

Schema for user registration.

```python
class UserCreate(BaseModel):
    """Schema for creating a new user"""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    roles: Optional[List[str]] = []
```

#### `UserRead`

Schema for user data response.

```python
class UserRead(BaseModel):
    """Schema for user data in responses"""

    id: UUID
    email: str
    username: str
    is_active: bool
    is_superuser: bool
    roles: List[str]
    created_at: datetime
    last_login: Optional[datetime]
```

#### `UserLogin`

Schema for user login.

```python
class UserLogin(BaseModel):
    """Schema for user login"""

    username: str
    password: str
```

#### `Token`

Schema for JWT token response.

```python
class Token(BaseModel):
    """Schema for JWT token"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int           # Seconds until expiration
```

#### `TokenData`

Schema for token payload.

```python
class TokenData(BaseModel):
    """Schema for decoded token data"""

    user_id: Optional[str] = None
    username: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
```

#### `PasswordReset`

Schema for password reset.

```python
class PasswordReset(BaseModel):
    """Schema for password reset request"""

    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""

    token: str
    new_password: str = Field(min_length=8)
```

#### `PasswordChange`

Schema for password change.

```python
class PasswordChange(BaseModel):
    """Schema for changing password"""

    current_password: str
    new_password: str = Field(min_length=8)
```

### API Routes (`routes.py`)

#### Authentication Endpoints

```
POST   /auth/register          # Register new user
POST   /auth/login             # Login and get token
POST   /auth/logout            # Logout (token blacklist)
GET    /auth/me                # Get current user
PUT    /auth/me                # Update current user
POST   /auth/password/reset    # Request password reset
POST   /auth/password/confirm  # Confirm password reset
PUT    /auth/password/change   # Change password
POST   /auth/refresh           # Refresh access token
```

#### Route Details

**Register User:**
```python
@router.post("/register", response_model=UserRead)
async def register(user_data: UserCreate):
    """Register a new user account"""
    pass
```

**Login:**
```python
@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate and return JWT token"""
    pass
```

**Get Current User:**
```python
@router.get("/me", response_model=UserRead)
async def get_current_user(user: User = Depends(get_current_user)):
    """Get currently authenticated user"""
    pass
```

### Service (`service.py`)

#### `AuthService`

Business logic for authentication.

```python
class AuthService:
    """Authentication business logic"""

    @staticmethod
    async def register(user_data: UserCreate) -> User:
        """Register a new user"""

    @staticmethod
    async def authenticate(username: str, password: str) -> Optional[User]:
        """Authenticate user credentials"""

    @staticmethod
    async def change_password(user: User, current: str, new: str) -> bool:
        """Change user password"""

    @staticmethod
    async def reset_password(email: str) -> str:
        """Generate password reset token"""

    @staticmethod
    async def confirm_reset(token: str, new_password: str) -> bool:
        """Confirm password reset"""
```

### Dependencies (`dependencies.py`)

#### `get_current_user`

FastAPI dependency to get authenticated user.

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get current authenticated user from JWT token.

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user": user.username}
    """
```

#### `get_current_active_user`

Get only active users.

```python
async def get_current_active_user(
    user: User = Depends(get_current_user)
) -> User:
    """Get current user only if account is active"""
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user
```

#### `get_current_superuser`

Get only superusers.

```python
async def get_current_superuser(
    user: User = Depends(get_current_user)
) -> User:
    """Get current user only if superuser"""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return user
```

#### `require_roles`

Require specific roles.

```python
def require_roles(required_roles: List[str]):
    """Dependency factory for role-based access"""

    async def role_checker(user: User = Depends(get_current_user)):
        user_roles = [role.name for role in user.roles]
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(status_code=403, detail="Insufficient roles")
        return user

    return role_checker
```

### Root User Initialization (`init_root.py`)

#### `init_root_user()`

Initialize the root/admin user on first run.

```python
async def init_root_user() -> None:
    """
    Create root user if no users exist.
    Credentials from environment variables:
    - ROOT_EMAIL (default: admin@localhost)
    - ROOT_PASSWORD (default: admin)
    """
```

## Usage Examples

### Basic Authentication

```python
from fastapi import FastAPI, Depends
from auth.routes import router as auth_router
from auth.dependencies import get_current_user
from auth.models import User

app = FastAPI()
app.include_router(auth_router, prefix="/auth")

@app.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"message": f"Hello {user.username}"}
```

### Using Authentication Service

```python
from auth.service import AuthService
from auth.schemas import UserCreate

# Register a new user
user_data = UserCreate(
    email="user@example.com",
    username="johndoe",
    password="securepassword"
)
user = await AuthService.register(user_data)

# Authenticate
user = await AuthService.authenticate("johndoe", "securepassword")
```

### Role-Based Access Control

```python
from fastapi import Depends
from auth.dependencies import require_roles

@app.get("/admin-only")
async def admin_route(
    user: User = Depends(require_roles(["admin"]))
):
    return {"message": "Admin access granted"}
```

### Password Management

```python
from auth.service import AuthService
from auth.schemas import PasswordChange

# Change password
await AuthService.change_password(
    user,
    current_password="oldpass",
    new_password="newpass"
)

# Reset password
token = await AuthService.reset_password("user@example.com")
# Send token via email...

# Confirm reset
await AuthService.confirm_reset(token, "newpassword")
```

## Configuration

Configuration in `config.json`:

```json
{
  "security": {
    "jwt_secret_key": "your-secret-key",
    "jwt_algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "refresh_token_expire_days": 7,
    "password_hash_algorithm": "bcrypt",
    "bcrypt_rounds": 12
  }
}
```

## Dependencies

- `fastapi` - Web framework
- `sqlalchemy` - Database ORM
- `passlib` - Password hashing
- `python-jose` - JWT handling
- `python-multipart` - Form data parsing

## Related Documentation

- [security.md](security.md) - Security utilities
- [admin.md](admin.md) - Administration (roles and permissions)
- [middleware.md](middleware.md) - Access control middleware
