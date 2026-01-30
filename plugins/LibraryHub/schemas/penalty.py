from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PenaltyBase(BaseModel):
    member_id: int
    amount: float
    reason: Optional[str] = None
    paid: Optional[str] = "No"


class PenaltyCreate(PenaltyBase):
    pass


class PenaltyUpdate(BaseModel):
    amount: Optional[float] = None
    reason: Optional[str] = None
    paid: Optional[str] = None


class PenaltyRead(PenaltyBase):
    id: int
    created_at: datetime




class PenaltyReadWithMember(PenaltyRead):
    member: dict
