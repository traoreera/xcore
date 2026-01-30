from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        String(30),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    role = Column(String(30), nullable=False, default="user")

    loans = relationship("Loan", back_populates="member", cascade="all, delete")
    penalties = relationship("Penalty", back_populates="member", cascade="all, delete")
    admin_logs = relationship("AdminLog", back_populates="admin", cascade="all, delete")

    def __repr__(self):
        return f"<Member {self.user_id}>"
