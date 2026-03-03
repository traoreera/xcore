from abc import ABC
from typing import Generic, List, Optional, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseAsyncRepository(ABC, Generic[T]):
    def __init__(self, model: T, session: AsyncSession = None):
        self.model = model
        self.session = session

    async def get_by_id(self, id: str) -> Optional[T]:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[T]:
        stmt = select(self.model)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, id: str, data) -> Optional[T]:
        stmt = update(self.model).where(self.model.id == id).values(data)
        response = await self.session.execute(stmt)
        await self.session.commit()
        return await response.scalar_one_or_none()

    async def delete(self, id: str) -> bool:
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def update_c9(self, data) -> Optional[T]:
        stmt = update(self.model).values(**data)
        response = await self.session.execute(stmt)
        await self.session.commit()
        return response.all()

    async def get_by_name(self, name: str) -> Optional[T]:
        stmt = select(self.model).where(self.model.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()
