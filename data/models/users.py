from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from data.schemas.users import UserCreate, UserResponse
from data.crud import make_uid

from data import Base
# 1. Define a Declarative Base


try:
    from security.hash import Hash
except:
    Hash = None









# 2. Define the User Model
class User(Base):
    __tablename__ = "users"  # Specifies the table name in the database

    id: Mapped[str] = mapped_column(String(30), primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    
    def responseModel(self):
        return UserResponse(username=self.username, email=self.email)



    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
