from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ipd_admission import IpdAdmission
from app.models.patient import Patient
from app.repositories.base import BaseRepository


class IpdAdmissionRepository(BaseRepository[IpdAdmission]):
    model = IpdAdmission

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_with_details(self, admission_id: str) -> IpdAdmission | None:
        result = await self.session.execute(
            select(IpdAdmission)
            .options(
                selectinload(IpdAdmission.patient),
                selectinload(IpdAdmission.ward),
                selectinload(IpdAdmission.doctor),
                selectinload(IpdAdmission.department),
            )
            .where(IpdAdmission.id == admission_id)
        )
        return result.scalar_one_or_none()

    async def get_by_admission_no(self, admission_no: str) -> IpdAdmission | None:
        result = await self.session.execute(
            select(IpdAdmission).where(
                IpdAdmission.admission_no == admission_no.strip().upper()
            )
        )
        return result.scalar_one_or_none()

    async def list_admissions(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        patient_id: str | None = None,
        limit: int = 100,
    ) -> list[IpdAdmission]:
        stmt = (
            select(IpdAdmission)
            .options(
                selectinload(IpdAdmission.patient),
                selectinload(IpdAdmission.ward),
                selectinload(IpdAdmission.doctor),
                selectinload(IpdAdmission.department),
            )
            .where(IpdAdmission.is_active.is_(True))
            .order_by(IpdAdmission.admission_date.desc(), IpdAdmission.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(IpdAdmission.status == status)
        if patient_id:
            stmt = stmt.where(IpdAdmission.patient_id == patient_id)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.join(Patient, IpdAdmission.patient_id == Patient.id).where(
                IpdAdmission.admission_no.ilike(term)
                | Patient.patient_no.ilike(term)
                | Patient.first_name.ilike(term)
                | Patient.last_name.ilike(term)
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_admitted_for_patient(self, patient_id: str) -> list[IpdAdmission]:
        return await self.list_admissions(status="admitted", patient_id=patient_id, limit=10)
