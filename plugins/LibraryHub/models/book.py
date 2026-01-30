from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..core import Base
from ..core.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    isbn = Column(String(50), unique=True, index=True)
    description = Column(String(500), nullable=True)
    published_year = Column(Integer, nullable=True)
    available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    author_id = Column(Integer, ForeignKey("authors.id", ondelete="SET NULL"))
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))

    author = relationship("Author", back_populates="books")
    category = relationship("Category", back_populates="books")
    loans = relationship("Loan", back_populates="book", cascade="all, delete")

    def __repr__(self):
        return f"<Book {self.title}>"
