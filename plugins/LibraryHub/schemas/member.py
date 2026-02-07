from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class MemberBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    is_admin: Optional[bool] = False


class MemberCreate(MemberBase):
    password: str


class MemberUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    password: Optional[str] = None


class MemberRead(MemberBase):
    id: int
    created_at: datetime
