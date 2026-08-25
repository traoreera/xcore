from abc import ABC
from typing import Generic, List, Optional, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseSyncRepository(ABC, Generic[T]):
    def __init__(self, model: T, session: Session):
        self.model = model
        self.session = session

    def get_by_id(self, id: str) -> Optional[T]:
        stmt = select(self.model).where(self.model.id == id)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def get_all(self) -> List[T]:
        stmt = select(self.model)
        result = self.session.execute(stmt)
        return result.scalars().all()

    def create(self, obj: T) -> T:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def update(self, id: str, data) -> Optional[T]:
        stmt = update(self.model).where(self.model.id == id).values(data)
        self.session.execute(stmt)
        self.session.commit()
        return self.get_by_id(id)

    def delete(self, id: str) -> bool:
        stmt = delete(self.model).where(self.model.id == id)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount > 0

    def get_by_name(self, name: str) -> Optional[T]:
        stmt = select(self.model).where(self.model.name == name)
        result = self.session.execute(stmt)
        return result.scalars().first()
