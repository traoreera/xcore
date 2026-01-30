from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class Penalty(Base):
    __tablename__ = "penalties"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"))
    amount = Column(Float, nullable=False)
    reason = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    paid = Column(String(10), default="No")  # Yes / No

    member = relationship("Member", back_populates="penalties")

    def __repr__(self):
        return f"<Penalty member={self.member_id} amount={self.amount}>"
