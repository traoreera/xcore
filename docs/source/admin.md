# admin - Administration & RBAC Module

## Overview

The `admin` module provides Role-Based Access Control (RBAC) with user management, role management, and permission management. It integrates with the `auth` module for user authentication and supports hierarchical permissions.

## Module Structure

```
admin/
├── __init__.py          # Module initialization
├── models.py            # Role & permission models
├── schemas.py           # Pydantic schemas
├── routes.py            # API endpoints
├── service.py           # Business logic
└── dependencies.py      # Admin authorization dependencies
```

## Core Components

### Models (`models.py`)

#### `Role`

SQLAlchemy model for user roles.

```python
class Role(Base):
    """Role model for RBAC"""

    __tablename__ = "roles"

    id: UUID                    # Unique role ID
    name: str                   # Role name (unique)
    description: str            # Role description
    permissions: List[Permission]  # Associated permissions
    users: List[User]           # Users with this role
    created_at: datetime        # Creation timestamp
    updated_at: datetime        # Last update timestamp
    is_system: bool             # System role (cannot delete)
```

#### `Permission`

SQLAlchemy model for permissions.

```python
class Permission(Base):
    """Permission model for RBAC"""

    __tablename__ = "permissions"

    id: UUID                    # Unique permission ID
    name: str                   # Permission name (unique)
    description: str            # Permission description
    resource: str               # Resource type (e.g., "users", "posts")
    action: str                 # Action (e.g., "create", "read", "update", "delete")
    roles: List[Role]           # Roles with this permission
    created_at: datetime        # Creation timestamp
```

#### Association Tables

```python
# Many-to-many: users <-> roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID, ForeignKey("users.id")),
    Column("role_id", UUID, ForeignKey("roles.id"))
)

# Many-to-many: roles <-> permissions
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID, ForeignKey("roles.id")),
    Column("permission_id", UUID, ForeignKey("permissions.id"))
)
```

### Schemas (`schemas.py`)

#### `RoleCreate`

```python
class RoleCreate(BaseModel):
    """Schema for creating a role"""

    name: str = Field(min_length=2, max_length=50)
    description: Optional[str]
    permission_ids: List[UUID] = []
```

#### `RoleUpdate`

```python
class RoleUpdate(BaseModel):
    """Schema for updating a role"""

    name: Optional[str] = Field(min_length=2, max_length=50)
    description: Optional[str]
    permission_ids: Optional[List[UUID]]
```

#### `RoleRead`

```python
class RoleRead(BaseModel):
    """Schema for role response"""

    id: UUID
    name: str
    description: Optional[str]
    permissions: List[PermissionRead]
    created_at: datetime
    is_system: bool
```

#### `PermissionCreate`

```python
class PermissionCreate(BaseModel):
    """Schema for creating a permission"""

    name: str = Field(min_length=2, max_length=50)
    description: Optional[str]
    resource: str
    action: str
```

#### `PermissionRead`

```python
class PermissionRead(BaseModel):
    """Schema for permission response"""

    id: UUID
    name: str
    description: Optional[str]
    resource: str
    action: str
    created_at: datetime
```

#### `UserRoleUpdate`

```python
class UserRoleUpdate(BaseModel):
    """Schema for updating user roles"""

    role_ids: List[UUID]
    operation: str = "set"  # "set", "add", "remove"
```

### API Routes (`routes.py`)

#### Role Management

```
GET    /admin/roles              # List all roles
POST   /admin/roles              # Create new role
GET    /admin/roles/{id}         # Get role details
PUT    /admin/roles/{id}         # Update role
DELETE /admin/roles/{id}         # Delete role
POST   /admin/roles/{id}/permissions  # Add permissions to role
DELETE /admin/roles/{id}/permissions  # Remove permissions from role
```

#### Permission Management

```
GET    /admin/permissions        # List all permissions
POST   /admin/permissions        # Create new permission
GET    /admin/permissions/{id}   # Get permission details
PUT    /admin/permissions/{id}   # Update permission
DELETE /admin/permissions/{id}   # Delete permission
```

#### User Management

```
GET    /admin/users              # List all users
GET    /admin/users/{id}         # Get user details
PUT    /admin/users/{id}/roles   # Update user roles
DELETE /admin/users/{id}         # Delete user
POST   /admin/users/{id}/activate    # Activate user
POST   /admin/users/{id}/deactivate  # Deactivate user
```

### Service (`service.py`)

#### `AdminService`

```python
class AdminService:
    """Administration business logic"""

    # Role management
    @staticmethod
    async def create_role(data: RoleCreate) -> Role:
        """Create a new role"""

    @staticmethod
    async def update_role(role_id: UUID, data: RoleUpdate) -> Role:
        """Update a role"""

    @staticmethod
    async def delete_role(role_id: UUID) -> None:
        """Delete a role (if not system role)"""

    @staticmethod
    async def add_permissions_to_role(role_id: UUID, permission_ids: List[UUID]) -> Role:
        """Add permissions to a role"""

    @staticmethod
    async def remove_permissions_from_role(role_id: UUID, permission_ids: List[UUID]) -> Role:
        """Remove permissions from a role"""

    # Permission management
    @staticmethod
    async def create_permission(data: PermissionCreate) -> Permission:
        """Create a new permission"""

    @staticmethod
    async def delete_permission(permission_id: UUID) -> None:
        """Delete a permission"""

    # User management
    @staticmethod
    async def update_user_roles(user_id: UUID, role_ids: List[UUID], operation: str = "set") -> User:
        """Update user roles"""

    @staticmethod
    async def activate_user(user_id: UUID) -> User:
        """Activate a user account"""

    @staticmethod
    async def deactivate_user(user_id: UUID) -> User:
        """Deactivate a user account"""
```

### Dependencies (`dependencies.py`)

#### `require_admin`

```python
async def require_admin(
    user: User = Depends(get_current_user)
) -> User:
    """
    Require admin role for access.

    Usage:
        @app.get("/admin-only")
        async def admin_route(user: User = Depends(require_admin)):
            pass
    """
```

#### `require_permission`

```python
def require_permission(resource: str, action: str):
    """
    Require specific permission for access.

    Usage:
        @app.get("/users")
        async def list_users(user: User = Depends(require_permission("users", "read"))):
            pass
    """
```

#### `check_user_permission`

```python
async def check_user_permission(
    user: User,
    resource: str,
    action: str
) -> bool:
    """Check if user has a specific permission"""
```

## Default Roles & Permissions

### System Roles

```python
DEFAULT_ROLES = [
    {
        "name": "admin",
        "description": "Full system access",
        "is_system": True,
        "permissions": ["*"]
    },
    {
        "name": "user",
        "description": "Standard user",
        "is_system": True,
        "permissions": ["users:read", "users:update"]
    },
    {
        "name": "moderator",
        "description": "Content moderator",
        "is_system": True,
        "permissions": ["content:read", "content:update", "content:delete"]
    }
]
```

### Default Permissions

```python
DEFAULT_PERMISSIONS = [
    # User permissions
    {"name": "users:create", "resource": "users", "action": "create"},
    {"name": "users:read", "resource": "users", "action": "read"},
    {"name": "users:update", "resource": "users", "action": "update"},
    {"name": "users:delete", "resource": "users", "action": "delete"},

    # Role permissions
    {"name": "roles:create", "resource": "roles", "action": "create"},
    {"name": "roles:read", "resource": "roles", "action": "read"},
    {"name": "roles:update", "resource": "roles", "action": "update"},
    {"name": "roles:delete", "resource": "roles", "action": "delete"},

    # Permission permissions
    {"name": "permissions:create", "resource": "permissions", "action": "create"},
    {"name": "permissions:read", "resource": "permissions", "action": "read"},
    {"name": "permissions:delete", "resource": "permissions", "action": "delete"},

    # Plugin permissions
    {"name": "plugins:install", "resource": "plugins", "action": "create"},
    {"name": "plugins:read", "resource": "plugins", "action": "read"},
    {"name": "plugins:update", "resource": "plugins", "action": "update"},
    {"name": "plugins:delete", "resource": "plugins", "action": "delete"},
    {"name": "plugins:enable", "resource": "plugins", "action": "enable"},
    {"name": "plugins:disable", "resource": "plugins", "action": "disable"},

    # Task permissions
    {"name": "tasks:create", "resource": "tasks", "action": "create"},
    {"name": "tasks:read", "resource": "tasks", "action": "read"},
    {"name": "tasks:update", "resource": "tasks", "action": "update"},
    {"name": "tasks:delete", "resource": "tasks", "action": "delete"},
]
```

## Usage Examples

### Basic Admin Routes

```python
from fastapi import FastAPI, Depends
from admin.routes import router as admin_router
from admin.dependencies import require_admin

app = FastAPI()
app.include_router(admin_router, prefix="/admin")

@app.get("/super-admin-only")
async def super_admin(user: User = Depends(require_admin)):
    return {"message": "Admin access granted"}
```

### Permission-Based Access

```python
from admin.dependencies import require_permission

@app.post("/posts")
async def create_post(
    post_data: PostCreate,
    user: User = Depends(require_permission("posts", "create"))
):
    return await create_post_service(post_data)

@app.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    user: User = Depends(require_permission("posts", "delete"))
):
    return await delete_post_service(post_id)
```

### Managing Roles

```python
from admin.service import AdminService
from admin.schemas import RoleCreate

# Create a role
role_data = RoleCreate(
    name="editor",
    description="Content editor",
    permission_ids=[uuid1, uuid2, uuid3]
)
role = await AdminService.create_role(role_data)

# Add permissions
await AdminService.add_permissions_to_role(
    role.id,
    [new_permission_id]
)

# Assign role to user
await AdminService.update_user_roles(
    user_id,
    [role.id],
    operation="add"
)
```

### Checking Permissions Programmatically

```python
from admin.dependencies import check_user_permission
from auth.dependencies import get_current_user

@app.get("/resource/{resource_id}")
async def get_resource(
    resource_id: str,
    user: User = Depends(get_current_user)
):
    # Check if user owns resource or has permission
    if resource.owner_id != user.id:
        has_permission = await check_user_permission(user, "resources", "read")
        if not has_permission:
            raise HTTPException(status_code=403, detail="Access denied")

    return resource
```

### Custom Permission Decorator

```python
def can_manage_users(func):
    """Decorator for user management endpoints"""
    return Depends(require_permission("users", "update"))(func)

@app.put("/users/{user_id}")
@can_manage_users
async def update_user(user_id: str, data: UserUpdate):
    pass
```

## Configuration

Configuration in `config.json`:

```json
{
  "middleware": {
    "access_rules": [
      {
        "path": "/admin/*",
        "roles": ["admin"],
        "permissions": []
      },
      {
        "path": "/manager/*",
        "roles": ["admin", "manager"],
        "permissions": ["plugins:read"]
      }
    ]
  }
}
```

## Integration with Middleware

The access control middleware uses the admin RBAC system:

```python
from middleware.access_control_Middleware import AccessControlMiddleware
from admin.dependencies import check_user_permission

# Middleware checks permissions for protected routes
middleware = AccessControlMiddleware(
    rules=config.middleware.access_rules
)
```

## Dependencies

- `auth` - Authentication module (User model)
- `database` - Database connection
- `fastapi` - Web framework
- `sqlalchemy` - Database ORM

## Related Documentation

- [auth.md](auth.md) - Authentication module
- [middleware.md](middleware.md) - Access control middleware
