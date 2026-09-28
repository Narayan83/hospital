from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.opd_bill import OpdBill, OpdBillPayment
from app.models.payment_mode import PaymentMode
from app.repositories.base import BaseRepository


class OpdBillRepository(BaseRepository[OpdBill]):
    model = OpdBill

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_with_lines(self, bill_id: str) -> OpdBill | None:
        result = await self.session.execute(
            select(OpdBill)
            .options(
                selectinload(OpdBill.lines),
                selectinload(OpdBill.patient),
                selectinload(OpdBill.doctor),
                selectinload(OpdBill.payment_mode),
                selectinload(OpdBill.payments).selectinload(OpdBillPayment.payment_mode).selectinload(PaymentMode.ledger),
                selectinload(OpdBill.department),
                selectinload(OpdBill.token),
            )
            .where(OpdBill.id == bill_id)
        )
        return result.scalar_one_or_none()

    async def get_by_bill_no(self, bill_no: str) -> OpdBill | None:
        result = await self.session.execute(
            select(OpdBill)
            .options(
                selectinload(OpdBill.lines),
                selectinload(OpdBill.patient),
                selectinload(OpdBill.doctor),
                selectinload(OpdBill.payment_mode),
                selectinload(OpdBill.payments).selectinload(OpdBillPayment.payment_mode).selectinload(PaymentMode.ledger),
                selectinload(OpdBill.department),
                selectinload(OpdBill.token),
            )
            .where(OpdBill.bill_no == bill_no.upper())
        )
        return result.scalar_one_or_none()

    async def list_by_patient_id(self, patient_id: str) -> list[OpdBill]:
        result = await self.session.execute(
            select(OpdBill)
            .options(
                selectinload(OpdBill.doctor),
                selectinload(OpdBill.department),
                selectinload(OpdBill.payment_mode),
                selectinload(OpdBill.payments)
                .selectinload(OpdBillPayment.payment_mode)
                .selectinload(PaymentMode.ledger),
                selectinload(OpdBill.token),
            )
            .where(OpdBill.patient_id == patient_id)
            .where(OpdBill.is_active.is_(True))
            .order_by(OpdBill.bill_date.desc(), OpdBill.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_patient_no(self, patient_no: str) -> list[OpdBill]:
        result = await self.session.execute(
            select(OpdBill)
            .options(
                selectinload(OpdBill.doctor),
                selectinload(OpdBill.department),
                selectinload(OpdBill.payment_mode),
                selectinload(OpdBill.payments)
                .selectinload(OpdBillPayment.payment_mode)
                .selectinload(PaymentMode.ledger),
                selectinload(OpdBill.token),
            )
            .where(OpdBill.patient_no == patient_no.strip())
            .where(OpdBill.is_active.is_(True))
            .order_by(OpdBill.bill_date.desc(), OpdBill.created_at.desc())
        )
        return list(result.scalars().all())
