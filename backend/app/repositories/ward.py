from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ward import Ward
from app.repositories.base import BaseRepository


class WardRepository(BaseRepository[Ward]):
    model = Ward

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[Ward]:
        result = await self.session.execute(
            select(Ward).where(Ward.is_active.is_(True)).order_by(Ward.sort_order, Ward.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Ward | None:
        result = await self.session.execute(select(Ward).where(Ward.code == code))
        return result.scalar_one_or_none()

    async def get_by_id(self, ward_id: str) -> Ward | None:
        result = await self.session.execute(select(Ward).where(Ward.id == ward_id))
        return result.scalar_one_or_none()
