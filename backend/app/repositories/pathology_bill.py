from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient import Patient
from app.models.pathology_bill import PathologyBill
from app.repositories.base import BaseRepository


class PathologyBillRepository(BaseRepository[PathologyBill]):
    model = PathologyBill

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_with_lines(self, bill_id: str) -> PathologyBill | None:
        result = await self.session.execute(
            select(PathologyBill)
            .options(
                selectinload(PathologyBill.lines),
                selectinload(PathologyBill.patient),
                selectinload(PathologyBill.doctor),
                selectinload(PathologyBill.payment_mode),
                selectinload(PathologyBill.department),
                selectinload(PathologyBill.order),
            )
            .where(PathologyBill.id == bill_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_lines_only(self, bill_id: str) -> PathologyBill | None:
        """Fetch a bill with only its lines loaded.

        Used while creating the pathology order for a brand-new bill: loading
        the (not-yet-created) ``order`` relationship here would cache it as
        None on the identity-mapped object for the rest of the request, hiding
        the order status from the create-bill response even after the order
        row is inserted moments later.
        """
        result = await self.session.execute(
            select(PathologyBill)
            .options(selectinload(PathologyBill.lines))
            .where(PathologyBill.id == bill_id)
        )
        return result.scalar_one_or_none()

    async def get_by_bill_no(self, bill_no: str) -> PathologyBill | None:
        result = await self.session.execute(
            select(PathologyBill)
            .options(
                selectinload(PathologyBill.lines),
                selectinload(PathologyBill.patient),
            )
            .where(PathologyBill.bill_no == bill_no.upper())
        )
        return result.scalar_one_or_none()

    async def list_bills(
        self,
        *,
        bill_date: date | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[PathologyBill]:
        stmt = (
            select(PathologyBill)
            .options(
                selectinload(PathologyBill.patient),
                selectinload(PathologyBill.doctor),
                selectinload(PathologyBill.lines),
            )
            .where(PathologyBill.is_active.is_(True))
            .order_by(PathologyBill.created_at.desc())
            .limit(limit)
        )
        if bill_date:
            stmt = stmt.where(PathologyBill.bill_date == bill_date)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.join(PathologyBill.patient).where(
                PathologyBill.bill_no.ilike(term)
                | PathologyBill.patient.has(patient_no=search.strip())
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_by_patient_id(self, patient_id: str) -> list[PathologyBill]:
        result = await self.session.execute(
            select(PathologyBill)
            .options(
                selectinload(PathologyBill.doctor),
                selectinload(PathologyBill.department),
                selectinload(PathologyBill.payment_mode),
                selectinload(PathologyBill.order),
            )
            .where(PathologyBill.patient_id == patient_id)
            .where(PathologyBill.is_active.is_(True))
            .order_by(PathologyBill.bill_date.desc(), PathologyBill.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_patient_no(self, patient_no: str) -> list[PathologyBill]:
        result = await self.session.execute(
            select(PathologyBill)
            .join(Patient, PathologyBill.patient_id == Patient.id)
            .options(
                selectinload(PathologyBill.doctor),
                selectinload(PathologyBill.department),
                selectinload(PathologyBill.payment_mode),
                selectinload(PathologyBill.order),
            )
            .where(Patient.patient_no == patient_no.strip())
            .where(PathologyBill.is_active.is_(True))
            .order_by(PathologyBill.bill_date.desc(), PathologyBill.created_at.desc())
        )
        return list(result.scalars().unique().all())
