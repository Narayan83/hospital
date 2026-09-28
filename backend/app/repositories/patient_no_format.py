from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient_no_format import PatientNoFormat
from app.repositories.base import BaseRepository


class PatientNoFormatRepository(BaseRepository[PatientNoFormat]):
    model = PatientNoFormat

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[PatientNoFormat]:
        result = await self.session.execute(
            select(PatientNoFormat)
            .where(PatientNoFormat.is_active.is_(True))
            .order_by(PatientNoFormat.sort_order, PatientNoFormat.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> PatientNoFormat | None:
        result = await self.session.execute(
            select(PatientNoFormat).where(PatientNoFormat.code == code)
        )
        return result.scalar_one_or_none()

    async def get_selected(self) -> PatientNoFormat | None:
        result = await self.session.execute(
            select(PatientNoFormat)
            .where(PatientNoFormat.is_active.is_(True))
            .where(PatientNoFormat.is_selected.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def clear_selected(self) -> None:
        await self.session.execute(
            update(PatientNoFormat).where(PatientNoFormat.is_selected.is_(True)).values(is_selected=False)
        )
