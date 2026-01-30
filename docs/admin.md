# Module Documentation: admin/

The `admin/` module is responsible for managing user roles and permissions within the `xcore` framework. It provides the necessary models, schemas, services, and API routes to handle role-based access control (RBAC) and administrative user management.

## Files and Their Roles

*   **`admin/__init__.py`**: (Likely empty or for package initialization).
*   **`admin/dependencies.py`**: Defines FastAPI dependency functions (`require_admin`, `require_superuser`) to enforce role-based access control on API routes. These dependencies ensure that only users with appropriate roles can access specific administrative endpoints.
*   **`admin/models.py`**: Contains SQLAlchemy ORM models (`Role`, `Permission`) and association tables (`user_roles`, `role_permissions`) that define the database schema for roles and permissions. These models establish many-to-many relationships between users, roles, and permissions.
*   **`admin/routes.py`**: Implements the FastAPI `APIRouter` for the `admin` module. It exposes various API endpoints for managing roles and permissions, all protected by the `require_admin` dependency.
*   **`admin/schemas.py`**: Defines Pydantic models (`RoleBase`, `RoleCreate`, `RoleRead`, `PermissionBase`, `PermissionCreate`, `PermissionRead`) for data validation and serialization. These schemas are used for defining the structure of request and response bodies for the `admin` API endpoints.
*   **`admin/service.py`**: Contains the core business logic for handling roles and permissions. This includes functions for creating, listing, deleting, and assigning roles and permissions, as well as an `init_root_admin` function for initial setup of a superuser.

## Key Concepts and Functionality

### Role-Based Access Control (RBAC)

The `admin` module implements RBAC through the `Role` and `Permission` models.
*   **Roles:** Represent collections of permissions that can be assigned to users (e.g., "admin", "superadmin", "editor").
*   **Permissions:** Granular authorizations for specific actions (e.g., "manage_users", "view_reports").
*   **User-Role Assignment:** Users can be assigned one or more roles.
*   **Role-Permission Assignment:** Roles can be assigned one or more permissions.

### Administrative Dependencies

*   `require_admin`: Ensures the current authenticated user has "root", "admin", or "superadmin" roles.
*   `require_superuser`: Ensures the current authenticated user has the "superadmin" role.

These dependencies are used in `admin/routes.py` to protect administrative endpoints, automatically returning a `403 Forbidden` error if the user lacks the necessary privileges.

### Root Admin Initialization

The `admin/service.py` includes an `init_root_admin` function which is crucial for the initial setup of the system. This function:
1.  Ensures a "superadmin" role exists.
2.  Creates a default root administrator user (`root@system.local` with a predefined password) if one does not already exist.
3.  Assigns the "superadmin" role to this root user.

### API Endpoints (`/admin`)

The `adminrouter` provides the following API endpoints:

*   **POST `/admin/roles`**: Create a new role.
*   **GET `/admin/roles`**: List all available roles.
*   **DELETE `/admin/roles/{role_id}`**: Delete a specific role.
*   **POST `/admin/users/{user_id}/roles/{role_id}`**: Assign a role to a specific user.
*   **POST `/admin/roles/{role_id}/permissions/{permission_id}`**: Assign a permission to a specific role.
*   **POST `/admin/permissions`**: Create a new permission.
*   **GET `/admin/permissions`**: List all available permissions.
*   **DELETE `/admin/permissions/{permission_id}`**: Delete a specific permission.

All these endpoints require administrative privileges as enforced by the `require_admin` dependency.

## Integration with Other Modules

*   **`auth/`**: Relies on the `auth` module's `get_current_user` dependency for user authentication and the `User` model for user management.
*   **`database/`**: Uses `database.db.get_db` for database session management.
*   **`security/`**: Utilizes `security.hash.Hash` for secure password hashing during root admin initialization.
*   **`xcore/view.py`**: The `adminrouter` from `admin/routes.py` is included in the main FastAPI application via `app.include_router(adminrouter)`.
