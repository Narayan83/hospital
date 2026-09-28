from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_structure import BillingStructureMapping
from app.models.billing_type import BillingType
from app.models.department import Department
from app.models.procedure_type import ProcedureType
from app.repositories.base import BaseRepository


class BillingStructureRepository(BaseRepository[BillingStructureMapping]):
    model = BillingStructureMapping

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[BillingStructureMapping]:
        result = await self.session.execute(
            select(BillingStructureMapping)
            .where(BillingStructureMapping.is_active.is_(True))
            .order_by(
                BillingStructureMapping.billing_type_id,
                BillingStructureMapping.department_id,
                BillingStructureMapping.sort_order,
            )
        )
        return list(result.scalars().all())

    async def lookup_master_maps(
        self,
    ) -> tuple[dict[str, BillingType], dict[str, Department], dict[str, ProcedureType]]:
        billing_types = {
            row.id: row
            for row in (await self.session.execute(select(BillingType))).scalars().all()
        }
        departments = {
            row.id: row
            for row in (await self.session.execute(select(Department))).scalars().all()
        }
        procedure_types = {
            row.id: row
            for row in (await self.session.execute(select(ProcedureType))).scalars().all()
        }
        return billing_types, departments, procedure_types

    async def get_by_id(self, mapping_id: str) -> BillingStructureMapping | None:
        result = await self.session.execute(
            select(BillingStructureMapping).where(BillingStructureMapping.id == mapping_id)
        )
        return result.scalar_one_or_none()

    async def get_combo(
        self, billing_type_id: str, department_id: str, procedure_type_id: str
    ) -> BillingStructureMapping | None:
        result = await self.session.execute(
            select(BillingStructureMapping).where(
                BillingStructureMapping.billing_type_id == billing_type_id,
                BillingStructureMapping.department_id == department_id,
                BillingStructureMapping.procedure_type_id == procedure_type_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_billing_type(self, billing_type_id: str) -> BillingType | None:
        result = await self.session.execute(
            select(BillingType).where(BillingType.id == billing_type_id)
        )
        return result.scalar_one_or_none()

    async def get_department(self, department_id: str) -> Department | None:
        result = await self.session.execute(select(Department).where(Department.id == department_id))
        return result.scalar_one_or_none()

    async def get_procedure_type(self, procedure_type_id: str) -> ProcedureType | None:
        result = await self.session.execute(
            select(ProcedureType).where(ProcedureType.id == procedure_type_id)
        )
        return result.scalar_one_or_none()
