from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from database import Base

# Table d’association
user_otp = Table(
    "user_otp",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("otp_id", Integer, ForeignKey("otp_devices.id")),
)


class OTPDevice(Base):
    __tablename__ = "otp_devices"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    secret = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_verified = Column(DateTime, nullable=True)

    users = relationship("User", secondary=user_otp, back_populates="opt")
