from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.db import get_db

from . import schemas, service, utils

optProvider = APIRouter(prefix="/otp", tags=["OTP Provider"])


@optProvider.post("/enable", response_model=schemas.OTPDeviceRead)
def enable_otp(payload: schemas.OTPDeviceCreate, db: Session = Depends(get_db)):
    otp_device = service.create_otp_device(db, payload.user_id)
    uri = utils.generate_qr_uri(otp_device.secret, f"user{otp_device.user_id}")
    return {**otp_device.__dict__, "provisioning_uri": uri}


@optProvider.post("/verify")
def verify_otp(payload: schemas.OTPVerifyRequest, db: Session = Depends(get_db)):
    return service.verify_otp(db, payload.user_id, payload.otp_code)
