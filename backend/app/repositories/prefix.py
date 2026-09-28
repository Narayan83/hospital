from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prefix import Prefix
from app.repositories.base import BaseRepository


class PrefixRepository(BaseRepository[Prefix]):
    model = Prefix

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[Prefix]:
        result = await self.session.execute(
            select(Prefix).where(Prefix.is_active.is_(True)).order_by(Prefix.sort_order, Prefix.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Prefix | None:
        wanted = (code or "").strip().upper()
        if not wanted:
            return None
        result = await self.session.execute(
            select(Prefix).where(func.upper(Prefix.code) == wanted)
        )
        return result.scalars().first()

    async def get_by_id(self, prefix_id: str) -> Prefix | None:
        result = await self.session.execute(select(Prefix).where(Prefix.id == prefix_id))
        return result.scalar_one_or_none()
