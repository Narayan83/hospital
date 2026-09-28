from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_type import BillingType
from app.models.department import Department
from app.models.doctor import Doctor
from app.models.hospital_section import HospitalSection
from app.models.patient import Patient
from app.models.patient_service_master import PatientServiceMaster
from app.models.payment_mode import PaymentMode
from app.models.user import User
from app.models.ward import Ward
from app.schemas.dashboard import DashboardStats


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _count(self, model, *, active_only: bool = False) -> int:
        query = select(func.count()).select_from(model)
        if active_only:
            query = query.where(model.is_active.is_(True))
        result = await self.session.execute(query)
        return int(result.scalar_one())

    async def get_stats(self) -> DashboardStats:
        return DashboardStats(
            patients=await self._count(Patient),
            doctors=await self._count(Doctor),
            departments=await self._count(Department, active_only=True),
            wards=await self._count(Ward),
            services=await self._count(PatientServiceMaster),
            staff=await self._count(User, active_only=True),
            billing_types=await self._count(BillingType, active_only=True),
            payment_modes=await self._count(PaymentMode, active_only=True),
            hospital_sections=await self._count(HospitalSection, active_only=True),
        )
