from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from data.crud import make_uid


class UserCreate(BaseModel):
    id: str = Field(default_factory=make_uid)
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    username: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class RemoveUser(BaseModel):
    email: EmailStr
    username: Optional[str] = None


class UpdateUser(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    model_config = ConfigDict(extra="ignore")

    def clean_dict(self):
        return {k: v for k, v in self.model_dump().items() if v is not None}


class UserPublic(BaseModel):
    id: str
    username: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserPublic):
    password: str


class UserDeleteResponse(BaseModel):
    status: str = Field(default="success")
    message: str = Field(default="Utilisateur supprimé avec succès")


class UserListResponse(BaseModel):
    total: int
    items: List[UserPublic]
