from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from . import models, schemas, utils


def create_otp_device(db: Session, user_id: int):
    """Crée un nouveau device OTP pour un utilisateur."""
    existing = (
        db.query(models.OTPDevice).filter(models.OTPDevice.user_id == user_id).first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Un OTP est déjà activé pour cet utilisateur."
        )

    secret = utils.generate_secret()
    otp_device = models.OTPDevice(user_id=user_id, secret=secret)
    db.add(otp_device)
    db.commit()
    db.refresh(otp_device)
    return otp_device


def verify_otp(db: Session, user_id: int, otp_code: str):
    """Vérifie le code TOTP envoyé par l’utilisateur."""
    otp_device = (
        db.query(models.OTPDevice)
        .filter(models.OTPDevice.user_id == user_id, models.OTPDevice.is_active == True)
        .first()
    )
    if not otp_device:
        raise HTTPException(status_code=404, detail="Aucun device OTP actif trouvé.")

    if not utils.verify_code(otp_device.secret, otp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Code OTP invalide."
        )

    otp_device.last_verified = datetime.utcnow()
    db.commit()
    return {"status": "verified", "user_id": user_id}


def deactivate_otp(db: Session, user_id: int):
    """Désactive le device OTP actif pour un utilisateur."""
    otp_device = (
        db.query(models.OTPDevice)
        .filter(models.OTPDevice.user_id == user_id, models.OTPDevice.is_active == True)
        .first()
    )
    if not otp_device:
        raise HTTPException(status_code=404, detail="Aucun device OTP actif trouve.")

    otp_device.is_active = False
    db.commit()
    return {"status": "deactivated", "user_id": user_id}
