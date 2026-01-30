from datetime import datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..core.database import Base


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"))
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"))
    borrowed_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=14))
    returned_at = Column(DateTime, nullable=True)
    is_late = Column(Boolean, default=False)

    book = relationship("Book", back_populates="loans")
    member = relationship("Member", back_populates="loans")

    def __repr__(self):
        return f"<Loan book={self.book_id} member={self.member_id}>"
