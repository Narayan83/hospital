from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.service_sub_category import ServiceSubCategory
from app.repositories.base import BaseRepository


class ServiceSubCategoryRepository(BaseRepository[ServiceSubCategory]):
    model = ServiceSubCategory

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self, category_id: str | None = None) -> list[ServiceSubCategory]:
        stmt = (
            select(ServiceSubCategory)
            .options(selectinload(ServiceSubCategory.category))
            .where(ServiceSubCategory.is_active.is_(True))
        )
        if category_id:
            stmt = stmt.where(ServiceSubCategory.category_id == category_id)
        stmt = stmt.order_by(ServiceSubCategory.sort_order, ServiceSubCategory.code)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category_code(
        self, category_id: str, code: str
    ) -> ServiceSubCategory | None:
        result = await self.session.execute(
            select(ServiceSubCategory)
            .where(ServiceSubCategory.category_id == category_id)
            .where(ServiceSubCategory.code == code.upper())
        )
        return result.scalar_one_or_none()
