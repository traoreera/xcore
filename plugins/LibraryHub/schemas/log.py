from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdminLogBase(BaseModel):
    action: str
    target: Optional[str] = None


class AdminLogCreate(AdminLogBase):
    admin_id: int


class AdminLogRead(AdminLogBase):
    id: int
    admin_id: int
    timestamp: datetime
