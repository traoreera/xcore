from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LoanBase(BaseModel):
    book_id: int
    member_id: int


class LoanCreate(LoanBase):
    due_date: Optional[datetime] = None


class LoanUpdate(BaseModel):
    returned_at: Optional[datetime] = None
    is_late: Optional[bool] = None


class LoanRead(BaseModel):
    id: int
    book_id: int
    member_id: int
    borrowed_at: datetime
    due_date: datetime
    returned_at: Optional[datetime] = None
    is_late: bool


