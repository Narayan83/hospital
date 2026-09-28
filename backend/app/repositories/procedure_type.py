from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.procedure_type import ProcedureType
from app.repositories.base import BaseRepository


class ProcedureTypeRepository(BaseRepository[ProcedureType]):
    model = ProcedureType

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[ProcedureType]:
        result = await self.session.execute(
            select(ProcedureType)
            .where(ProcedureType.is_active.is_(True))
            .order_by(ProcedureType.sort_order, ProcedureType.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> ProcedureType | None:
        result = await self.session.execute(select(ProcedureType).where(ProcedureType.code == code))
        return result.scalar_one_or_none()

    async def get_by_id(self, procedure_type_id: str) -> ProcedureType | None:
        result = await self.session.execute(
            select(ProcedureType).where(ProcedureType.id == procedure_type_id)
        )
        return result.scalar_one_or_none()
