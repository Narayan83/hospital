from fastapi import HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession



from app.models.ledger import Ledger

from app.models.payment_mode import PaymentMode

from app.repositories.ledger import LedgerRepository

from app.repositories.payment_mode import PaymentModeRepository

from app.schemas.payment_mode import PaymentModeCreate, PaymentModeRead, PaymentModeUpdate





class PaymentModeService:

    def __init__(self, session: AsyncSession):

        self.repo = PaymentModeRepository(session)

        self.ledger_repo = LedgerRepository(session)



    def _to_read(self, item: PaymentMode) -> PaymentModeRead:

        ledger = item.ledger

        return PaymentModeRead(

            id=item.id,

            code=item.code,

            name=item.name,

            is_cash=item.is_cash,

            ledger_id=item.ledger_id,

            ledger_code=ledger.code if ledger else None,

            ledger_name=ledger.name if ledger else None,

            sort_order=item.sort_order,

            is_active=item.is_active,

            created_at=item.created_at,

            updated_at=item.updated_at,

        )



    async def _validate_ledger(self, ledger_id: str | None) -> None:

        if not ledger_id:

            return

        ledger = await self.ledger_repo.get_by_id(ledger_id)

        if not ledger or not ledger.is_active:

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ledger not found")



    async def list_payment_modes(self) -> list[PaymentModeRead]:

        items = await self.repo.list_active()

        return [self._to_read(item) for item in items]



    async def get_payment_mode(self, payment_mode_id: str) -> PaymentModeRead:

        item = await self.repo.get_by_id(payment_mode_id)

        if not item or not item.is_active:

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment mode not found")

        return self._to_read(item)



    async def create_payment_mode(self, data: PaymentModeCreate) -> PaymentModeRead:

        await self._validate_ledger(data.ledger_id)

        code = data.code.strip().upper()

        existing = await self.repo.get_by_code(code)

        if existing:

            if existing.is_active:

                raise HTTPException(

                    status_code=status.HTTP_400_BAD_REQUEST,

                    detail="Payment mode code already exists",

                )

            existing.name = data.name.strip()

            existing.is_cash = data.is_cash

            existing.ledger_id = data.ledger_id

            existing.sort_order = data.sort_order

            existing.is_active = True

            await self.repo.session.flush()

            await self.repo.session.refresh(existing)

            refreshed = await self.repo.get_by_id(existing.id)

            return self._to_read(refreshed)  # type: ignore[arg-type]



        item = PaymentMode(

            code=code,

            name=data.name.strip(),

            is_cash=data.is_cash,

            ledger_id=data.ledger_id,

            sort_order=data.sort_order,

            is_active=data.is_active,

        )

        self.repo.session.add(item)

        await self.repo.session.flush()

        await self.repo.session.refresh(item)

        refreshed = await self.repo.get_by_id(item.id)

        return self._to_read(refreshed)  # type: ignore[arg-type]



    async def update_payment_mode(

        self, payment_mode_id: str, data: PaymentModeUpdate

    ) -> PaymentModeRead:

        item = await self.repo.get_by_id(payment_mode_id)

        if not item or not item.is_active:

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment mode not found")

        payload = data.model_dump(exclude_unset=True)

        if "ledger_id" in payload:

            await self._validate_ledger(payload.get("ledger_id"))

        for field, value in payload.items():

            if field == "name" and value is not None:

                value = value.strip()

            setattr(item, field, value)

        await self.repo.session.flush()

        await self.repo.session.refresh(item)

        refreshed = await self.repo.get_by_id(item.id)

        return self._to_read(refreshed)  # type: ignore[arg-type]



    async def delete_payment_mode(self, payment_mode_id: str) -> PaymentModeRead:

        item = await self.repo.get_by_id(payment_mode_id)

        if not item or not item.is_active:

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment mode not found")

        item.is_active = False

        await self.repo.session.flush()

        await self.repo.session.refresh(item)

        refreshed = await self.repo.get_by_id(item.id)

        return self._to_read(refreshed)  # type: ignore[arg-type]

