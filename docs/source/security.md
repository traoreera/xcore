# security - Security Utilities Module

## Overview

The `security` module provides security utilities including password hashing, JWT token creation/verification, and cryptographic helpers.

## Module Structure

```
security/
├── __init__.py          # Module exports
├── conf.py              # Security configuration
├── hash.py              # Password hashing (bcrypt)
└── token.py             # JWT token creation/verification
```

## Core Components

### Password Hashing (`hash.py`)

#### `get_password_hash()`

Hash a password using bcrypt.

```python
def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string

    Usage:
        hashed = get_password_hash("my_password")
    """
```

#### `verify_password()`

Verify a password against a hash.

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hash.

    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise

    Usage:
        if verify_password("my_password", stored_hash):
            print("Password correct")
    """
```

### JWT Tokens (`token.py`)

#### `create_access_token()`

Create a JWT access token.

```python
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in token (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string

    Usage:
        token = create_access_token(
            data={"sub": str(user.id), "roles": ["user"]},
            expires_delta=timedelta(minutes=30)
        )
    """
```

#### `create_refresh_token()`

Create a JWT refresh token.

```python
def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token with longer expiration.

    Args:
        data: Data to encode in token

    Returns:
        JWT refresh token string

    Usage:
        refresh = create_refresh_token({"sub": str(user.id)})
    """
```

#### `verify_token()`

Verify and decode a JWT token.

```python
def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token data or None if invalid

    Usage:
        payload = verify_token(token)
        if payload:
            user_id = payload.get("sub")
    """
```

#### `decode_token()`

Decode token without verification (for debugging).

```python
def decode_token(token: str) -> dict:
    """
    Decode token without signature verification.

    WARNING: Only use for debugging, not for authentication!

    Args:
        token: JWT token string

    Returns:
        Decoded token payload
    """
```

## Usage Examples

### Password Hashing

```python
from security.hash import get_password_hash, verify_password

# Hash password for storage
password = "user_password"
hashed_password = get_password_hash(password)
# Store hashed_password in database

# Verify password during login
is_valid = verify_password("user_password", stored_hash)
if is_valid:
    print("Login successful")
else:
    print("Invalid password")
```

### User Registration

```python
from security.hash import get_password_hash
from auth.models import User

def register_user(email: str, password: str, db: Session):
    # Hash the password
    hashed_password = get_password_hash(password)

    # Create user with hashed password
    user = User(
        email=email,
        hashed_password=hashed_password
    )
    db.add(user)
    db.commit()
    return user
```

### User Authentication

```python
from security.hash import verify_password
from security.token import create_access_token
from datetime import timedelta

def authenticate_user(email: str, password: str, db: Session):
    # Get user from database
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    # Verify password
    if not verify_password(password, user.hashed_password):
        return None

    # Create access token
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "roles": [role.name for role in user.roles]
        },
        expires_delta=timedelta(minutes=30)
    )

    return {"access_token": token, "token_type": "bearer"}
```

### Token Creation

```python
from security.token import create_access_token, create_refresh_token
from datetime import timedelta

# Create access token
access_token = create_access_token(
    data={
        "sub": str(user.id),
        "type": "access"
    },
    expires_delta=timedelta(minutes=30)
)

# Create refresh token
refresh_token = create_refresh_token(
    data={
        "sub": str(user.id),
        "type": "refresh"
    }
)
```

### Token Verification

```python
from security.token import verify_token
from fastapi import HTTPException, status

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    return get_user_by_id(user_id)
```

### Refresh Token Flow

```python
from security.token import verify_token, create_access_token
from fastapi import HTTPException

async def refresh_access_token(refresh_token: str):
    # Verify refresh token
    payload = verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    user = await get_user_by_id(user_id)

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Create new access token
    new_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "roles": [role.name for role in user.roles]
        }
    )

    return {"access_token": new_token, "token_type": "bearer"}
```

## Configuration

Configuration in `config.json`:

```json
{
  "security": {
    "jwt_secret_key": "your-secret-key-change-in-production",
    "jwt_algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "refresh_token_expire_days": 7,
    "password_hash_algorithm": "bcrypt",
    "bcrypt_rounds": 12
  }
}
```

### Environment Variables

```bash
# Security settings (use in production!)
export JWT_SECRET_KEY="super-secret-random-string"
export JWT_ALGORITHM="HS256"
export BCRYPT_ROUNDS=12
```

## Best Practices

### 1. Keep Secrets Secret

```python
# Good - use environment variable
import os
SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# Bad - hardcoded secret
SECRET_KEY = "my-secret-key"
```

### 2. Use Appropriate Token Expiration

```python
# Short-lived access tokens
def create_access_token(data: dict):
    return _create_token(
        data,
        expires_delta=timedelta(minutes=15)  # 15 minutes
    )

# Longer-lived refresh tokens
def create_refresh_token(data: dict):
    return _create_token(
        data,
        expires_delta=timedelta(days=7)  # 7 days
    )
```

### 3. Include Minimal Data in Tokens

```python
# Good - minimal data
token_data = {
    "sub": str(user.id),  # Subject (user ID)
    "type": "access"
}

# Bad - too much data
token_data = {
    "user": user.dict(),  # Don't put entire user object
    "permissions": all_permissions,
    "settings": user.settings
}
```

### 4. Always Verify Passwords Correctly

```python
# Good - constant-time comparison
if verify_password(input_password, stored_hash):
    # Success

# Bad - timing attack vulnerable
if input_password == stored_password:  # Never do this!
    # Success
```

### 5. Handle Token Errors Gracefully

```python
from fastapi import HTTPException, status

def verify_token_safe(token: str):
    try:
        return verify_token(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
```

## API Integration

### FastAPI OAuth2

```python
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from security.token import verify_token

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Authenticate user
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # Create token
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = verify_token(token)
    user = await get_user_by_id(payload.get("sub"))
    return user
```

## Dependencies

- `passlib` - Password hashing
- `bcrypt` - Bcrypt implementation
- `python-jose` - JWT handling
- `configurations` - Security configuration

## Related Documentation

- [auth.md](auth.md) - Authentication module
- [configurations.md](configurations.md) - Security configuration
