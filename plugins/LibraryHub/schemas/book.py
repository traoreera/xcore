from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BookBase(BaseModel):
    title: str
    isbn: str
    description: Optional[str] = None
    published_year: Optional[int] = None
    available: Optional[bool] = True
    author_id: Optional[int] = None
    category_id: Optional[int] = None


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    published_year: Optional[int] = None
    available: Optional[bool] = None
    author_id: Optional[int] = None
    category_id: Optional[int] = None


class BookRead(BookBase):
    id: int
    created_at: datetime
