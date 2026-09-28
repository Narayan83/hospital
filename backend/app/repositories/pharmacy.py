from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pharmacy import PharmacyCodeMaster, PharmacyGroupMapping, PharmacyItem, PharmacySupplier
from app.repositories.base import BaseRepository


class PharmacyCodeMasterRepository(BaseRepository[PharmacyCodeMaster]):
    model = PharmacyCodeMaster

    async def list_active(self, master_type: str) -> list[PharmacyCodeMaster]:
        result = await self.session.execute(
            select(PharmacyCodeMaster)
            .where(
                PharmacyCodeMaster.master_type == master_type,
                PharmacyCodeMaster.is_active.is_(True),
            )
            .order_by(PharmacyCodeMaster.sort_order, PharmacyCodeMaster.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, master_type: str, code: str) -> PharmacyCodeMaster | None:
        result = await self.session.execute(
            select(PharmacyCodeMaster).where(
                PharmacyCodeMaster.master_type == master_type,
                PharmacyCodeMaster.code == code,
            )
        )
        return result.scalar_one_or_none()


class PharmacyItemRepository(BaseRepository[PharmacyItem]):
    model = PharmacyItem

    async def list_active(self, item_type: str) -> list[PharmacyItem]:
        result = await self.session.execute(
            select(PharmacyItem)
            .where(
                PharmacyItem.item_type == item_type,
                PharmacyItem.is_active.is_(True),
            )
            .order_by(PharmacyItem.sort_order, PharmacyItem.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, item_type: str, code: str) -> PharmacyItem | None:
        result = await self.session.execute(
            select(PharmacyItem).where(
                PharmacyItem.item_type == item_type,
                PharmacyItem.code == code,
            )
        )
        return result.scalar_one_or_none()

    async def search(self, item_type: str, query: str, limit: int = 25) -> list[PharmacyItem]:
        text = query.strip()
        if not text:
            return []
        pattern = f"%{text}%"
        result = await self.session.execute(
            select(PharmacyItem)
            .where(
                PharmacyItem.item_type == item_type.upper(),
                PharmacyItem.is_active.is_(True),
                or_(
                    PharmacyItem.code.ilike(pattern),
                    PharmacyItem.name.ilike(pattern),
                    PharmacyItem.generic_name.ilike(pattern),
                ),
            )
            .order_by(PharmacyItem.name)
            .limit(limit)
        )
        return list(result.scalars().all())


class PharmacySupplierRepository(BaseRepository[PharmacySupplier]):
    model = PharmacySupplier

    async def list_active(self) -> list[PharmacySupplier]:
        result = await self.session.execute(
            select(PharmacySupplier)
            .where(PharmacySupplier.is_active.is_(True))
            .order_by(PharmacySupplier.sort_order, PharmacySupplier.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> PharmacySupplier | None:
        result = await self.session.execute(
            select(PharmacySupplier).where(PharmacySupplier.code == code)
        )
        return result.scalar_one_or_none()


class PharmacyGroupMappingRepository(BaseRepository[PharmacyGroupMapping]):
    model = PharmacyGroupMapping

    async def list_by_group(self, group_id: str) -> list[PharmacyGroupMapping]:
        result = await self.session.execute(
            select(PharmacyGroupMapping)
            .where(PharmacyGroupMapping.group_id == group_id)
            .order_by(PharmacyGroupMapping.created_at)
        )
        return list(result.scalars().all())

    async def get_mapping(self, group_id: str, item_id: str) -> PharmacyGroupMapping | None:
        result = await self.session.execute(
            select(PharmacyGroupMapping).where(
                PharmacyGroupMapping.group_id == group_id,
                PharmacyGroupMapping.item_id == item_id,
            )
        )
        return result.scalar_one_or_none()
