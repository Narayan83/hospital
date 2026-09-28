from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload



from app.models.ipd_bill import IpdBill, IpdBillPayment
from app.models.payment_mode import PaymentMode

from app.repositories.base import BaseRepository





class IpdBillRepository(BaseRepository[IpdBill]):

    model = IpdBill



    def __init__(self, session: AsyncSession):

        super().__init__(session)



    async def get_with_lines(self, bill_id: str) -> IpdBill | None:

        result = await self.session.execute(

            select(IpdBill)

            .options(

                selectinload(IpdBill.lines),

                selectinload(IpdBill.patient),

                selectinload(IpdBill.admission),

                selectinload(IpdBill.ward),

                selectinload(IpdBill.doctor),

                selectinload(IpdBill.department),

                selectinload(IpdBill.payment_mode),

                selectinload(IpdBill.payments).selectinload(IpdBillPayment.payment_mode).selectinload(PaymentMode.ledger),

            )

            .where(IpdBill.id == bill_id)

        )

        return result.scalar_one_or_none()



    async def get_by_bill_no(self, bill_no: str) -> IpdBill | None:

        result = await self.session.execute(

            select(IpdBill)

            .options(

                selectinload(IpdBill.lines),

                selectinload(IpdBill.patient),

                selectinload(IpdBill.admission),

            )

            .where(IpdBill.bill_no == bill_no.strip().upper())

        )

        return result.scalar_one_or_none()



    async def get_by_admission_id(self, admission_id: str) -> IpdBill | None:

        result = await self.session.execute(

            select(IpdBill).where(

                IpdBill.admission_id == admission_id,

                IpdBill.is_active.is_(True),

            )

        )

        return result.scalar_one_or_none()

    async def list_by_patient_id(self, patient_id: str) -> list[IpdBill]:
        result = await self.session.execute(
            select(IpdBill)
            .options(
                selectinload(IpdBill.doctor),
                selectinload(IpdBill.ward),
                selectinload(IpdBill.admission),
                selectinload(IpdBill.payment_mode),
                selectinload(IpdBill.payments)
                .selectinload(IpdBillPayment.payment_mode)
                .selectinload(PaymentMode.ledger),
            )
            .where(IpdBill.patient_id == patient_id)
            .where(IpdBill.is_active.is_(True))
            .order_by(IpdBill.bill_date.desc(), IpdBill.created_at.desc())
        )
        return list(result.scalars().all())

