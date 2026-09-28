from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_category import ServiceCategory
from app.repositories.base import BaseRepository


class ServiceCategoryRepository(BaseRepository[ServiceCategory]):
    model = ServiceCategory

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[ServiceCategory]:
        result = await self.session.execute(
            select(ServiceCategory)
            .where(ServiceCategory.is_active.is_(True))
            .order_by(ServiceCategory.sort_order, ServiceCategory.code)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> ServiceCategory | None:
        result = await self.session.execute(
            select(ServiceCategory).where(ServiceCategory.code == code)
        )
        return result.scalar_one_or_none()
