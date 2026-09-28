from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing_package import BillingPackage, BillingPackageItem
from app.repositories.base import BaseRepository


class BillingPackageRepository(BaseRepository[BillingPackage]):
    model = BillingPackage

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[tuple[BillingPackage, int]]:
        item_count = func.count(BillingPackageItem.id).label("item_count")
        result = await self.session.execute(
            select(BillingPackage, item_count)
            .outerjoin(
                BillingPackageItem,
                (BillingPackageItem.package_id == BillingPackage.id)
                & (BillingPackageItem.is_active.is_(True)),
            )
            .where(BillingPackage.is_active.is_(True))
            .group_by(BillingPackage.id)
            .order_by(BillingPackage.sort_order, BillingPackage.code)
        )
        return list(result.all())

    async def get_by_code(self, code: str) -> BillingPackage | None:
        result = await self.session.execute(
            select(BillingPackage).where(BillingPackage.code == code)
        )
        return result.scalar_one_or_none()

    async def get_with_items(self, package_id: str) -> BillingPackage | None:
        result = await self.session.execute(
            select(BillingPackage)
            .options(
                selectinload(BillingPackage.items).selectinload(BillingPackageItem.service)
            )
            .where(BillingPackage.id == package_id)
        )
        return result.scalar_one_or_none()
