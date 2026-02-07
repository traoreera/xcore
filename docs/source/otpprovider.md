# otpprovider - One-Time Password (OTP) Services Module

## Overview

The `otpprovider` module provides two-factor authentication (2FA) support using time-based one-time passwords (TOTP). It includes OTP generation, verification, and QR code creation for authenticator apps.

## Module Structure

```
otpprovider/
├── __init__.py          # Module exports
├── models.py            # OTP models
├── schemas.py           # OTP schemas
├── routes.py            # OTP API endpoints
├── service.py           # OTP generation/verification
├── utils.py             # OTP utilities
└── dependencies.py      # OTP dependencies
```

## Core Components

### Models (`models.py`)

#### `OTPDevice`

SQLAlchemy model for OTP devices.

```python
class OTPDevice(Base):
    """OTP device for 2FA"""

    __tablename__ = "otp_devices"

    id: UUID                    # Unique device ID
    user_id: UUID               # Associated user ID
    name: str                   # Device name (e.g., "iPhone", "Authenticator")
    secret: str                 # TOTP secret (encrypted)
    confirmed: bool             # Device confirmed
    created_at: datetime        # Creation timestamp
    last_used_at: datetime      # Last verification timestamp
    is_active: bool             # Device active status
    backup_codes: List[str]     # Encrypted backup codes
    digits: int                 # OTP length (default: 6)
    interval: int               # TOTP interval in seconds (default: 30)
```

### Schemas (`schemas.py`)

#### `OTPEnrollment`

```python
class OTPEnrollment(BaseModel):
    """Schema for OTP enrollment"""

    device_name: str = Field(default="Authenticator")
```

#### `OTPEnrollmentResponse`

```python
class OTPEnrollmentResponse(BaseModel):
    """Response after starting enrollment"""

    device_id: UUID
    secret: str                  # TOTP secret (shown once)
    qr_code_url: str             # QR code for authenticator apps
    manual_entry_key: str        # Key for manual entry
    backup_codes: List[str]      # One-time backup codes
```

#### `OTPVerification`

```python
class OTPVerification(BaseModel):
    """Schema for OTP verification"""

    device_id: UUID
    code: str = Field(min_length=6, max_length=6)
```

#### `OTPConfirmation`

```python
class OTPConfirmation(BaseModel):
    """Schema for confirming enrollment"""

    device_id: UUID
    code: str
```

#### `OTPDisable`

```python
class OTPDisable(BaseModel):
    """Schema for disabling 2FA"""

    password: str                # Current password confirmation
    code: Optional[str]          # Optional TOTP code
```

### API Routes (`routes.py`)

#### OTP Management Endpoints

```
POST   /otp/enroll             # Start 2FA enrollment
POST   /otp/confirm            # Confirm enrollment with code
POST   /otp/verify             # Verify TOTP code
POST   /otp/disable            # Disable 2FA
GET    /otp/devices            # List user's OTP devices
DELETE /otp/devices/{id}       # Remove a device
POST   /otp/backup-codes       # Generate new backup codes
```

### Service (`service.py`)

#### `OTPService`

```python
class OTPService:
    """Service for OTP operations"""

    @staticmethod
    def generate_secret() -> str:
        """Generate new TOTP secret"""

    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Generate one-time backup codes"""

    @staticmethod
    def generate_qr_code_uri(
        secret: str,
        user_email: str,
        issuer: str = "xcore"
    ) -> str:
        """Generate QR code URI for authenticator apps"""

    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        """Verify TOTP code"""

    @staticmethod
    def verify_backup_code(
        device: OTPDevice,
        code: str
    ) -> bool:
        """Verify and consume a backup code"""

    @staticmethod
    def generate_qr_code_image(uri: str) -> bytes:
        """Generate QR code image (PNG)"""
```

### Utilities (`utils.py`)

```python
def encrypt_secret(secret: str) -> str:
    """Encrypt TOTP secret for storage"""

def decrypt_secret(encrypted: str) -> str:
    """Decrypt TOTP secret"""

def hash_backup_code(code: str) -> str:
    """Hash backup code for storage"""

def verify_backup_code_hash(code: str, hashed: str) -> bool:
    """Verify backup code against hash"""

def generate_provisioning_uri(
    secret: str,
    user_email: str,
    issuer: str
) -> str:
    """Generate provisioning URI for QR code"""
```

### Dependencies (`dependencies.py`)

#### `require_otp_verified`

```python
async def require_otp_verified(
    user: User = Depends(get_current_user)
) -> User:
    """
    Require OTP verification for sensitive operations.

    Usage:
        @app.post("/sensitive-action")
        async def sensitive_action(
            user: User = Depends(require_otp_verified)
        ):
            pass
    """
```

#### `verify_otp_if_enabled`

```python
async def verify_otp_if_enabled(
    user: User = Depends(get_current_user),
    otp_code: Optional[str] = Header(None, alias="X-OTP-Code")
) -> User:
    """
    Verify OTP if user has 2FA enabled.

    Usage:
        @app.post("/action")
        async def action(
            user: User = Depends(verify_otp_if_enabled)
        ):
            pass
    """
```

## Usage Examples

### Enabling 2FA

```python
from otpprovider.service import OTPService
from otpprovider.schemas import OTPEnrollmentResponse

# Start enrollment
async def enable_2fa(user: User):
    # Generate secret
    secret = OTPService.generate_secret()

    # Create device
    device = OTPDevice(
        user_id=user.id,
        name="Authenticator",
        secret=encrypt_secret(secret),
        confirmed=False
    )

    # Generate QR code
    qr_uri = OTPService.generate_qr_code_uri(
        secret=secret,
        user_email=user.email,
        issuer="MyApp"
    )

    # Generate backup codes
    backup_codes = OTPService.generate_backup_codes(10)
    device.backup_codes = [hash_backup_code(c) for c in backup_codes]

    return OTPEnrollmentResponse(
        device_id=device.id,
        secret=secret,  # Show only once
        qr_code_url=qr_uri,
        manual_entry_key=secret,
        backup_codes=backup_codes  # Show only once
    )
```

### Verifying OTP

```python
from otpprovider.service import OTPService
from otpprovider.utils import decrypt_secret

async def verify_login(user: User, code: str):
    # Get user's active device
    device = await get_active_device(user.id)

    if not device:
        # No 2FA enabled
        return complete_login(user)

    # Decrypt secret
    secret = decrypt_secret(device.secret)

    # Verify code
    if OTPService.verify_code(secret, code):
        # Update last used
        device.last_used_at = datetime.utcnow()
        await save_device(device)
        return complete_login(user)

    # Try backup code
    if OTPService.verify_backup_code(device, code):
        return complete_login(user)

    raise HTTPException(status_code=401, detail="Invalid OTP code")
```

### Complete 2FA Flow

```python
# 1. User initiates 2FA setup
@app.post("/otp/enroll")
async def enroll(
    enrollment: OTPEnrollment,
    user: User = Depends(get_current_user)
):
    return await enable_2fa(user, enrollment.device_name)

# 2. User confirms with code from authenticator
@app.post("/otp/confirm")
async def confirm(
    confirmation: OTPConfirmation,
    user: User = Depends(get_current_user)
):
    device = await get_device(confirmation.device_id)

    # Verify code
    secret = decrypt_secret(device.secret)
    if OTPService.verify_code(secret, confirmation.code):
        device.confirmed = True
        await save_device(device)
        return {"status": "confirmed"}

    raise HTTPException(status_code=400, detail="Invalid code")

# 3. User logs in with 2FA
@app.post("/auth/login")
async def login(
    credentials: UserLogin,
    otp_code: Optional[str] = Header(None, alias="X-OTP-Code")
):
    # Authenticate credentials
    user = await authenticate(credentials)

    # Check if 2FA enabled
    if await has_active_device(user.id):
        if not otp_code:
            return {"requires_2fa": True}

        if not await verify_login(user, otp_code):
            raise HTTPException(status_code=401, detail="Invalid OTP")

    return create_tokens(user)
```

### Using Dependencies

```python
from fastapi import Depends
from otpprovider.dependencies import require_otp_verified, verify_otp_if_enabled

# Require OTP for sensitive action
@app.post("/api/transfer-funds")
async def transfer_funds(
    transfer: TransferRequest,
    user: User = Depends(require_otp_verified)
):
    # User has verified OTP recently
    return await process_transfer(transfer)

# Verify OTP if enabled
@app.delete("/api/account")
async def delete_account(
    user: User = Depends(verify_otp_if_enabled)
):
    # User either has no 2FA or provided valid code
    return await process_deletion(user)
```

### Disabling 2FA

```python
@app.post("/otp/disable")
async def disable_2fa(
    request: OTPDisable,
    user: User = Depends(get_current_user)
):
    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")

    # If 2FA enabled, verify OTP code
    if await has_active_device(user.id):
        if not request.code:
            raise HTTPException(status_code=400, detail="OTP code required")

        device = await get_active_device(user.id)
        secret = decrypt_secret(device.secret)

        if not OTPService.verify_code(secret, request.code):
            raise HTTPException(status_code=401, detail="Invalid OTP")

    # Disable all devices
    await disable_all_devices(user.id)
    return {"status": "disabled"}
```

## Configuration

Configuration in `config.json`:

```json
{
  "otp": {
    "enabled": true,
    "digits": 6,
    "interval": 30,
    "issuer_name": "xcore",
    "backup_codes_count": 10,
    "max_devices_per_user": 5,
    "verification_window": 1,
    "require_otp_for_sensitive": true
  }
}
```

### Environment Variables

```bash
export OTP_ENABLED=true
export OTP_ISSUER="MyApp"
export OTP_ENCRYPTION_KEY="secret-key-for-otp"
```

## Authenticator App Support

### Compatible Apps

- Google Authenticator
- Microsoft Authenticator
- Authy
- 1Password
- LastPass Authenticator
- FreeOTP
- andOTP

### QR Code Format

```
otpauth://totp/{issuer}:{user_email}?
    secret={secret}&
    issuer={issuer}&
    algorithm=SHA1&
    digits=6&
    period=30
```

## Security Considerations

### 1. Secret Encryption

```python
# Always encrypt TOTP secrets
device.secret = encrypt_secret(secret)

# Never store in plain text
# device.secret = secret  # DON'T DO THIS
```

### 2. Backup Codes

```python
# Store hashed backup codes
device.backup_codes = [
    hash_backup_code(code)
    for code in backup_codes
]

# Show only once during enrollment
return OTPEnrollmentResponse(
    backup_codes=backup_codes  # User must save these
)
```

### 3. Rate Limiting

```python
from fastapi import Request
from slowapi import Limiter

limiter = Limiter(key_func=lambda: request.client.host)

@app.post("/otp/verify")
@limiter.limit("5/minute")
async def verify(request: Request, verification: OTPVerification):
    pass
```

## Testing

### Mock OTP Service

```python
@pytest.fixture
def mock_otp_service():
    class MockOTPService:
        @staticmethod
        def generate_secret():
            return "MOCKSECRET123456"

        @staticmethod
        def verify_code(secret, code):
            return code == "123456"

    return MockOTPService()

async def test_otp_verification(mock_otp_service):
    assert mock_otp_service.verify_code("secret", "123456")
    assert not mock_otp_service.verify_code("secret", "000000")
```

### Testing TOTP

```python
import pyotp

def test_totp_generation():
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)

    # Generate code
    code = totp.now()

    # Verify code
    assert totp.verify(code)

    # Verify with window
    assert totp.verify(code, valid_window=1)
```

## Troubleshooting

### Common Issues

1. **"Invalid code" errors**
   - Check system time is synchronized
   - Verify secret was transferred correctly
   - Try with valid_window=1

2. **QR code not scanning**
   - Ensure high contrast
   - Make sure URI format is correct
   - Try manual entry

3. **Backup codes not working**
   - Check if already used
   - Verify hashing is consistent
   - Ensure codes are stored encrypted

## Dependencies

- `pyotp` - TOTP implementation
- `qrcode` - QR code generation
- `cryptography` - Secret encryption
- `fastapi` - API framework

## Related Documentation

- [auth.md](auth.md) - Authentication module
- [security.md](security.md) - Security utilities
