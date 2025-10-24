from pydantic import BaseModel, EmailStr


class OTPDeviceCreate(BaseModel):
    user_id: int


class OTPDeviceRead(BaseModel):
    id: int
    user_id: int
    secret: str
    is_active: bool

    class Config:
        from_attributes = True


class OTPVerifyRequest(BaseModel):
    user_id: int
    otp_code: str
