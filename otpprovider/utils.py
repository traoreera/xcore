import pyotp


def generate_secret():
    """Génère un secret base32 compatible avec Google Authenticator."""
    return pyotp.random_base32()


def get_totp(secret: str):
    return pyotp.TOTP(secret)


def generate_qr_uri(secret: str, email: str, issuer: str = "FastAPIApp"):
    """Retourne l’URI pour QR Code compatible Google Authenticator."""
    return f"otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}"


def verify_code(secret: str, code: str):
    """Vérifie la validité du code TOTP."""
    totp = get_totp(secret)
    return totp.verify(code, valid_window=1)
