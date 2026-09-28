from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload



from app.models.payment_mode import PaymentMode

from app.repositories.base import BaseRepository





class PaymentModeRepository(BaseRepository[PaymentMode]):

    model = PaymentMode



    def __init__(self, session: AsyncSession):

        super().__init__(session)



    async def list_active(self) -> list[PaymentMode]:

        result = await self.session.execute(

            select(PaymentMode)

            .options(selectinload(PaymentMode.ledger))

            .where(PaymentMode.is_active.is_(True))

            .order_by(PaymentMode.sort_order, PaymentMode.name)

        )

        return list(result.scalars().all())



    async def get_by_code(self, code: str) -> PaymentMode | None:

        result = await self.session.execute(

            select(PaymentMode)

            .options(selectinload(PaymentMode.ledger))

            .where(PaymentMode.code == code.upper())

        )

        return result.scalar_one_or_none()



    async def get_by_id(self, payment_mode_id: str) -> PaymentMode | None:
        result = await self.session.execute(
            select(PaymentMode)
            .options(selectinload(PaymentMode.ledger))
            .where(PaymentMode.id == payment_mode_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ledger_id(self, ledger_id: str) -> PaymentMode | None:
        result = await self.session.execute(
            select(PaymentMode)
            .options(selectinload(PaymentMode.ledger))
            .where(PaymentMode.ledger_id == ledger_id)
            .where(PaymentMode.is_active.is_(True))
            .order_by(PaymentMode.sort_order, PaymentMode.name)
            .limit(1)
        )
        return result.scalar_one_or_none()

