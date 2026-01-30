from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"))
    action = Column(String(255), nullable=False)
    target = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    admin = relationship("Member", back_populates="admin_logs")

    def __repr__(self):
        return f"<AdminLog admin={self.admin_id} action={self.action}>"
