from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_type import BillingType
from app.repositories.base import BaseRepository


class BillingTypeRepository(BaseRepository[BillingType]):
    model = BillingType

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[BillingType]:
        result = await self.session.execute(
            select(BillingType)
            .where(BillingType.is_active.is_(True))
            .order_by(BillingType.sort_order, BillingType.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> BillingType | None:
        result = await self.session.execute(select(BillingType).where(BillingType.code == code))
        return result.scalar_one_or_none()

    async def get_by_id(self, billing_type_id: str) -> BillingType | None:
        result = await self.session.execute(
            select(BillingType).where(BillingType.id == billing_type_id)
        )
        return result.scalar_one_or_none()
