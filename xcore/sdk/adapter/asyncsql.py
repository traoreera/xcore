from abc import ABC
from typing import Generic, List, Optional, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseAsyncRepository(ABC, Generic[T]):
    def __init__(self, model: T):
        self.model = model

    async def get_by_id(self, session:AsyncSession, id: str) -> Optional[T]:
        stmt = select(self.model).where(self.model.id == id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, session:AsyncSession) -> List[T]:
        stmt = select(self.model)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create(self,session:AsyncSession, obj: T) -> T:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    async def update(self, session:AsyncSession,id: str, data) -> Optional[T]:
        stmt = update(self.model).where(self.model.id == id).values(data)
        response = await session.execute(stmt)
        await session.commit()
        return await response.scalar_one_or_none()

    async def delete(self,session:AsyncSession, id: str) -> bool:
        stmt = delete(self.model).where(self.model.id == id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    async def update_c9(self,session:AsyncSession,  data) -> Optional[T]:
        stmt = update(self.model).values(**data)
        response = await session.execute(stmt)
        await session.commit()
        return response.all()

    async def get_by_name(self,session:AsyncSession, name: str) -> Optional[T]:
        stmt = select(self.model).where(self.model.name == name)
        result = await session.execute(stmt)
        return result.scalars().first()
