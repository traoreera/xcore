from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

    books = relationship("Book", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"
