# Module Documentation: security/

The `security/` module provides foundational components for securing the `xcore` application, primarily focusing on password management (hashing and verification) and JWT (JSON Web Token) based authentication and authorization. It centralizes cryptographic operations and token handling.

## Files and Their Roles

*   **`security/__init__.py`**: (Likely empty or for package initialization).
*   **`security/conf.py`**: Handles loading security-specific configurations from `config.json` (via `configurations.secure.Secure`) and environment variables. It defines the `TokenConfig` class to encapsulate JWT-related settings.
*   **`security/hash.py`**: Implements secure password hashing and verification using the `passlib` library, abstracting away the complexities of cryptographic algorithms.
*   **`security/token.py`**: Provides static methods for creating, encoding, decoding, and verifying JWTs, which are essential for stateless authentication in FastAPI applications.

## Key Concepts and Functionality

### Configuration Loading (`security/conf.py`)

The `security/conf.py` file ensures that security settings are loaded in a prioritized manner:
1.  **`config.json`**: Base security configuration (e.g., preferred password hashing schemes) is loaded from the `secure` section of `config.json`.
2.  **Environment Variables (`.env`)**: Sensitive information, particularly for JWTs, is expected to be provided via environment variables (e.g., `JWTKEY`, `ALGORITHM`, `ISSUER`, `ACCESS_TOKEN_EXPIRE_MINUTES`). These are crucial for the integrity of the JWTs. The path to the `.env` file can be configured in `config.json` (`secure.dotenv`).

### Password Hashing (`security/hash.py`)

The `Hash` class provides a secure way to manage user passwords:
*   **Algorithm Agnostic**: It uses `passlib.context.CryptContext` to support various password hashing algorithms, configurable via `config.json` (`secure.password.scheme`). The default is "bcrypt", a strong, industry-standard algorithm.
*   **`Hash.hash(password: str)`**: Takes a plain-text password and returns its secure hash. This hash is stored in the database instead of the raw password.
*   **`Hash.verify(hashed_password: str, plain_password: str)`**: Compares a plain-text password against a stored hash. This method handles the cryptographic comparison securely.
*   **Password Re-hashing**: It includes logic to detect if a stored password hash needs to be updated (e.g., if a stronger algorithm is adopted or iteration count changes), allowing for seamless migration of hashes.

### JWT Token Management (`security/token.py`)

The `Token` class centralizes the creation and validation of JWTs:
*   **`Token.create(data: dict) -> str`**:
    *   Generates a new JWT.
    *   It takes a `data` payload (e.g., `{"sub": user_email}`).
    *   Automatically adds an `exp` (expiration) claim based on `TokenConfig.ACCESS_TOKEN_EXPIRE_MINUTES`.
    *   The token is then signed using the secret key (`TokenConfig.JWTKEY`) and algorithm (`TokenConfig.ALGORITHM`) defined in `security/conf.py`.
*   **`Token.verify(token: str, credentials_exception: HTTPException) -> dict`**:
    *   Validates an incoming JWT.
    *   It decodes the token using the configured key and algorithm.
    *   Checks for token validity, including expiration and signature.
    *   If the token is valid, it returns the decoded payload. If invalid, it raises a `credentials_exception` (typically an `HTTPException` with `401 Unauthorized` status).

## Integration with Other Modules

*   **`auth/`**: The `auth` module heavily relies on `security.hash.py` for password hashing during user registration and verification during login. It also uses `security.token.py` to create and verify JWTs for authentication.
*   **`middleware/access_control_Middleware.py`**: This middleware uses `security.token.Token.verify` to validate incoming JWTs before enforcing access control rules.
*   **`configurations/secure.py`**: Provides the structured configuration for `security/hash.py` and the `.env` file path for `security/conf.py`.
*   **Environment Variables**: `JWTKEY`, `ALGORITHM`, `ISSUER`, and `ACCESS_TOKEN_EXPIRE_MINUTES` are crucial environment variables that must be set (e.g., in a `.env` file) for the JWT functionality to work correctly.
