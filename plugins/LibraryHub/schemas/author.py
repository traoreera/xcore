from typing import Optional

from pydantic import BaseModel


class AuthorBase(BaseModel):
    name: str
    bio: Optional[str] = None
    nationality: Optional[str] = None


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    nationality: Optional[str] = None


class AuthorRead(AuthorBase):
    pass
