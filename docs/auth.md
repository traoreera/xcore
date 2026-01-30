# Module Documentation: auth/

The `auth/` module provides comprehensive authentication and user management functionalities for the `xcore` framework. It handles user registration, login, token generation, and defines dependencies for protecting API routes.

## Files and Their Roles

*   **`auth/__init__.py`**: (Likely empty or for package initialization).
*   **`auth/dependencies.py`**: Defines FastAPI dependency functions for authentication. Key functions include `OAuth2PasswordBearer` for token extraction and `get_current_user` for validating JWT tokens and fetching the corresponding user from the database.
*   **`auth/init_root.py`**: A script responsible for the initial setup of a "root" user and a "root" role in the system if they do not already exist. It also configures an OTP (One-Time Password) device for the root user, enabling 2FA.
*   **`auth/models.py`**: Contains the SQLAlchemy ORM model (`User`) that defines the database schema for users. It includes fields for `email`, `password_hash`, `is_active`, and establishes relationships with `Role` (from `admin` module) and `OTPDevice` (from `otpprovider` module).
*   **`auth/routes.py`**: Implements the FastAPI `APIRouter` for the `auth` module. It exposes API endpoints for user registration, login, and fetching the current user's details.
*   **`auth/schemas.py`**: Defines Pydantic models (`UserCreate`, `UserRead`, `Token`) for data validation and serialization. These schemas are used for defining the structure of request and response bodies for the `auth` API endpoints.
*   **`auth/service.py`**: Contains the core business logic for user authentication and registration. This includes functions like `register_user` (to create new users with hashed passwords) and `authenticate_user` (to verify user credentials).

## Key Concepts and Functionality

### User Authentication with JWT and OAuth2

The `auth` module implements token-based authentication using JWT (JSON Web Tokens) and the OAuth2 password flow.
*   **`OAuth2PasswordBearer`**: Used to extract the token from the `Authorization` header.
*   **`get_current_user`**: This dependency decodes and verifies the JWT token. If the token is valid, it retrieves the associated `User` object from the database, making it available to route functions.

### User Management

*   **Registration**: Users can create new accounts by providing an email and password via the `/auth/register` endpoint. Passwords are securely hashed before being stored.
*   **Login**: Users can authenticate using their email and password via the `/auth/login` endpoint, which returns an `access_token` (JWT) that can be used to access protected routes.
*   **Current User Details**: The `/auth/me` endpoint allows an authenticated user to retrieve their own profile information.

### Root User Initialization

The `init_root.py` script is a critical part of the system setup. It ensures that an initial "root" administrator account is available, complete with a default password (which should be changed immediately) and a pre-configured OTP for two-factor authentication. This provides a secure bootstrap for the administrative interface.

### Data Models and Schemas

*   **`User` Model**: Represents a user in the database, storing their email, hashed password, and active status. It links to roles and OTP devices.
*   **Pydantic Schemas**: Facilitate clear API contracts for user creation (`UserCreate`), reading user data (`UserRead`), and token handling (`Token`).

## API Endpoints (`/auth`)

The `authRouter` provides the following API endpoints:

*   **POST `/auth/register`**:
    *   **Description**: Registers a new user account.
    *   **Request Body**: `UserCreate` (email, password).
    *   **Response**: `UserRead` (id, email, is_active).
*   **POST `/auth/login`**:
    *   **Description**: Authenticates a user and returns an access token.
    *   **Request Body**: Form data (username=email, password).
    *   **Response**: `Token` (access_token, token_type).
*   **GET `/auth/me`**:
    *   **Description**: Retrieves the details of the currently authenticated user.
    *   **Authentication**: Requires a valid JWT in the `Authorization` header.
    *   **Response**: `UserRead` (id, email, is_active). This endpoint is also cached for performance.

## Integration with Other Modules

*   **`admin/`**: The `auth` module's `User` model and `get_current_user` dependency are used by the `admin` module for role assignment and access control.
*   **`database/`**: Relies on `database.db.get_db` for database session management.
*   **`security/`**: Uses `security.token.Token` for JWT creation and `security.hash.Hash` for password hashing and verification.
*   **`otpprovider/`**: Interacts with the `otpprovider` module for OTP device management and generation during root user setup.
*   **`xcore/view.py`**: The `authRouter` from `auth/routes.py` is included in the main FastAPI application via `app.include_router(authRouter)`.
