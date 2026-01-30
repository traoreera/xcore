from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    bio = Column(Text, nullable=True)
    nationality = Column(String(100), nullable=True)

    books = relationship("Book", back_populates="author", cascade="all, delete")

    def __repr__(self):
        return f"<Author {self.name}>"

    def __str__(self):
        return self.name
