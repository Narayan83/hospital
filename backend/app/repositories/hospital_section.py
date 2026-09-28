from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hospital_section import HospitalSection
from app.repositories.base import BaseRepository


class HospitalSectionRepository(BaseRepository[HospitalSection]):
    model = HospitalSection

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[HospitalSection]:
        result = await self.session.execute(
            select(HospitalSection)
            .where(HospitalSection.is_active.is_(True))
            .order_by(HospitalSection.sort_order, HospitalSection.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> HospitalSection | None:
        result = await self.session.execute(
            select(HospitalSection).where(HospitalSection.code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, section_id: str) -> HospitalSection | None:
        result = await self.session.execute(
            select(HospitalSection).where(HospitalSection.id == section_id)
        )
        return result.scalar_one_or_none()
