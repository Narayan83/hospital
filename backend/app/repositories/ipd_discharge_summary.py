from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ipd_admission import IpdAdmission
from app.models.ipd_discharge_summary import IpdDischargeSummary
from app.models.patient import Patient
from app.repositories.base import BaseRepository


class IpdDischargeSummaryRepository(BaseRepository[IpdDischargeSummary]):
    model = IpdDischargeSummary

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_with_details(self, summary_id: str) -> IpdDischargeSummary | None:
        result = await self.session.execute(
            select(IpdDischargeSummary)
            .options(
                selectinload(IpdDischargeSummary.admission).selectinload(IpdAdmission.ward),
                selectinload(IpdDischargeSummary.admission).selectinload(IpdAdmission.department),
                selectinload(IpdDischargeSummary.admission).selectinload(IpdAdmission.doctor),
                selectinload(IpdDischargeSummary.patient),
                selectinload(IpdDischargeSummary.doctor),
            )
            .where(IpdDischargeSummary.id == summary_id)
        )
        return result.scalar_one_or_none()

    async def get_by_summary_no(self, summary_no: str) -> IpdDischargeSummary | None:
        result = await self.session.execute(
            select(IpdDischargeSummary).where(
                IpdDischargeSummary.summary_no == summary_no.strip().upper()
            )
        )
        return result.scalar_one_or_none()

    async def get_by_admission_id(self, admission_id: str) -> IpdDischargeSummary | None:
        result = await self.session.execute(
            select(IpdDischargeSummary).where(
                IpdDischargeSummary.admission_id == admission_id,
                IpdDischargeSummary.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_summaries(
        self,
        *,
        search: str | None = None,
        patient_id: str | None = None,
        patient_no: str | None = None,
        admission_id: str | None = None,
        limit: int = 100,
    ) -> list[IpdDischargeSummary]:
        stmt = (
            select(IpdDischargeSummary)
            .options(
                selectinload(IpdDischargeSummary.admission),
                selectinload(IpdDischargeSummary.patient),
                selectinload(IpdDischargeSummary.doctor),
            )
            .where(IpdDischargeSummary.is_active.is_(True))
            .order_by(IpdDischargeSummary.summary_date.desc(), IpdDischargeSummary.created_at.desc())
            .limit(limit)
        )
        joined_patient = False
        if patient_id:
            stmt = stmt.where(IpdDischargeSummary.patient_id == patient_id)
        if patient_no:
            stmt = stmt.join(Patient, IpdDischargeSummary.patient_id == Patient.id)
            joined_patient = True
            stmt = stmt.where(Patient.patient_no.ilike(patient_no.strip()))
        if admission_id:
            stmt = stmt.where(IpdDischargeSummary.admission_id == admission_id)
        if search:
            term = f"%{search.strip()}%"
            if not joined_patient:
                stmt = stmt.join(Patient, IpdDischargeSummary.patient_id == Patient.id)
            stmt = stmt.where(
                IpdDischargeSummary.summary_no.ilike(term)
                | Patient.patient_no.ilike(term)
                | Patient.first_name.ilike(term)
                | Patient.last_name.ilike(term)
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())
