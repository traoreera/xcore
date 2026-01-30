# Module Documentation: middleware/

The `middleware/` module contains custom FastAPI middleware designed to enhance the application's functionality, primarily focusing on security and access control. Middleware components intercept incoming requests and outgoing responses, allowing for centralized processing before or after route handling.

## Files and Their Roles

*   **`middleware/__init__.py`**: (Likely empty or for package initialization).
*   **`middleware/access_control_Middleware.py`**: Implements a robust access control mechanism based on JWT tokens, user roles, permissions, and HTTP methods, enforcing granular authorization policies.

## Key Concepts and Functionality

### Access Control Middleware (`AccessControlMiddleware`)

The `AccessControlMiddleware` is a critical security component that integrates with FastAPI's request-response cycle. It provides a configurable way to protect API endpoints and ensure that only authorized users with the correct privileges can access specific resources.

**How it Works:**

1.  **Initialization**: The middleware is initialized with the FastAPI `app` instance and a set of `access_rules`. These rules are typically loaded from the `config.json` file under `xcore.middleware.ACCESS_RULES`.
2.  **Request Dispatch (`dispatch` method)**: For every incoming request, the `dispatch` method performs the following steps:
    *   **Rule Matching**: It first attempts to match the incoming request's path and HTTP method against the configured `access_rules`. Rules can specify exact paths or use wildcards (e.g., `/admin/*` to match all paths under `/admin`).
    *   **JWT Extraction & Verification**: If a matching rule is found, it extracts the JWT (JSON Web Token) from the `Authorization: Bearer <token>` header. The token is then verified for authenticity and expiry using `security.token.Token.verify`.
        *   Missing or invalid tokens result in a `401 Unauthorized` response.
    *   **User Retrieval**: The middleware retrieves the `User` object from the database using the user's identifier (subject) from the verified JWT payload.
    *   **User Status Check**: It verifies if the retrieved user exists and is active.
        *   Inactive or unknown users result in a `403 Forbidden` response.
    *   **Role and Permission Enforcement**: The middleware then compares the authenticated user's assigned roles and permissions (fetched from the database relationships) against the `required_roles` and `required_perms` specified in the matched `access_rule`.
        *   If the user lacks any required role or permission, a `403 Forbidden` response is returned.
    *   **Request Continuation**: If all security checks pass, the request is passed to the next middleware or the appropriate FastAPI route handler (`call_next(request)`).

**Configuration (`config.json`)**:

The `access_rules` are defined in `config.json` (under `xcore.middleware.ACCESS_RULES`), allowing for flexible and dynamic configuration of access policies without code changes:

```json
"xcore": {
    "middleware": {
        "ACCESS_RULES": {
            "/admin/roles": {
                "roles": ["admin", "superadmin"] // Only users with 'admin' or 'superadmin' role can access
            },
            "/admin/permissions": {
                "permissions": ["manage_permissions"],
                "roles": ["admin"],
                "method": ["DELETE"] // Specific permission for DELETE method for 'admin' role
            },
            "/users": {
                "roles": ["superadmin"],
                "method": "DELETE" // Only 'superadmin' can DELETE /users
            },
            "/reports*": {
                "permissions": ["view_reports"] // Users with 'view_reports' permission can access any path under /reports
            }
        }
    }
}
```

## Integration with Other Modules

*   **`auth/models.py`**: The middleware relies on the `User` model from the `auth` module to retrieve user details and their associated roles and permissions.
*   **`database/db.py`**: Uses the `get_db` dependency to obtain a SQLAlchemy session for querying user information.
*   **`security/token.py`**: Utilizes the `Token` class from the `security` module to verify JWT access tokens.
*   **`xcore/appcfg.py`**: The `xcfg` object (which loads `config.json`) is used to retrieve the `access_rules` for the middleware.
*   **`main.py`**: The `AccessControlMiddleware` is typically added to the FastAPI application instance in `main.py` (though it might be commented out by default, indicating it's an optional feature).
