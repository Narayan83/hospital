from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.authority import Authority
from app.repositories.base import BaseRepository


class AuthorityRepository(BaseRepository[Authority]):
    model = Authority

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[Authority]:
        result = await self.session.execute(
            select(Authority)
            .where(Authority.is_active.is_(True))
            .order_by(Authority.sort_order, Authority.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Authority | None:
        result = await self.session.execute(select(Authority).where(Authority.code == code))
        return result.scalar_one_or_none()

    async def get_by_id(self, authority_id: str) -> Authority | None:
        result = await self.session.execute(select(Authority).where(Authority.id == authority_id))
        return result.scalar_one_or_none()
