from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from admin.models import Role, user_roles
from database import Base
from dependencies import make_ids
from otpprovider.models import OTPDevice, user_otp


class User(Base):
    __tablename__ = "users"
    id = Column(String(30), primary_key=True, index=True, default=make_ids())
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)

    roles = relationship("Role", secondary=user_roles, back_populates="users")
    opt = relationship("OTPDevice", back_populates="users", secondary=user_otp)

    def responseModel(self):
        return {
            "email": self.email,
            "is_active": self.is_active,
            "roles": [role.name for role in self.roles],
        }
