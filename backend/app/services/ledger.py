from decimal import Decimal



from fastapi import HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession



from app.models.ledger import LEDGER_TYPES, Ledger

from app.repositories.ledger import LedgerRepository

from app.schemas.ledger import LedgerCreate, LedgerRead, LedgerUpdate





def signed_opening_balance(ledger: Ledger) -> Decimal:

    """Debit-positive opening used in cashbook / daybook statements."""

    amount = abs(Decimal(str(ledger.opening_balance or 0)))

    if (ledger.ledger_type or "").upper() in ("LIABILITY", "INCOME"):

        return -amount

    return amount





class LedgerService:

    def __init__(self, session: AsyncSession):

        self.repo = LedgerRepository(session)



    async def list_ledgers(self) -> list[LedgerRead]:

        items = await self.repo.list_active()

        return [LedgerRead.model_validate(item) for item in items]



    async def get_ledger(self, ledger_id: str) -> LedgerRead:

        item = await self.repo.get_by_id(ledger_id)

        if not item or not item.is_active:

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger not found")

        return LedgerRead.model_validate(item)



    def _normalize_flags(

        self,

        *,

        is_cash: bool,

        is_bank: bool,

        is_patient_deposit: bool,

    ) -> tuple[bool, bool, bool]:

        if is_cash and is_bank:

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="A ledger cannot be both Cash and Bank",

            )

        return bool(is_cash), bool(is_bank), bool(is_patient_deposit)



    def _normalize_type(self, ledger_type: str) -> str:

        value = (ledger_type or "ASSET").strip().upper()

        if value not in LEDGER_TYPES:

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail=f"Invalid ledger type. Use one of: {', '.join(LEDGER_TYPES)}",

            )

        return value



    async def create_ledger(self, data: LedgerCreate) -> LedgerRead:

        code = data.code.strip().upper()

        ledger_type = self._normalize_type(data.ledger_type)

        is_cash, is_bank, is_patient_deposit = self._normalize_flags(

            is_cash=data.is_cash,

            is_bank=data.is_bank,

            is_patient_deposit=data.is_patient_deposit,

        )

        opening = Decimal(str(data.opening_balance or 0))



        existing = await self.repo.get_by_code(code)

        if existing:

            if existing.is_active:

                raise HTTPException(

                    status_code=status.HTTP_400_BAD_REQUEST,

                    detail="Ledger code already exists",

                )

            existing.name = data.name.strip()

            existing.ledger_type = ledger_type

            existing.opening_balance = opening

            existing.is_cash = is_cash

            existing.is_bank = is_bank

            existing.is_patient_deposit = is_patient_deposit

            existing.sort_order = data.sort_order

            existing.is_active = True

            await self.repo.session.flush()

            await self.repo.session.refresh(existing)

            return LedgerRead.model_validate(existing)



        item = Ledger(

            code=code,

            name=data.name.strip(),

            ledger_type=ledger_type,

            opening_balance=opening,

            is_cash=is_cash,

            is_bank=is_bank,

            is_patient_deposit=is_patient_deposit,

            sort_order=data.sort_order,

            is_active=True,

        )

        self.repo.session.add(item)

        await self.repo.session.flush()

        await self.repo.session.refresh(item)

        return LedgerRead.model_validate(item)



    async def update_ledger(self, ledger_id: str, data: LedgerUpdate) -> LedgerRead:

        item = await self.repo.get_by_id(ledger_id)

        if not item or not item.is_active:

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger not found")



        payload = data.model_dump(exclude_unset=True)

        if "name" in payload and payload["name"] is not None:

            payload["name"] = payload["name"].strip()

        if "ledger_type" in payload and payload["ledger_type"] is not None:

            payload["ledger_type"] = self._normalize_type(payload["ledger_type"])



        is_cash = payload.get("is_cash", item.is_cash)

        is_bank = payload.get("is_bank", item.is_bank)

        is_patient_deposit = payload.get("is_patient_deposit", item.is_patient_deposit)

        is_cash, is_bank, is_patient_deposit = self._normalize_flags(

            is_cash=is_cash,

            is_bank=is_bank,

            is_patient_deposit=is_patient_deposit,

        )

        if "is_cash" in payload or "is_bank" in payload or "is_patient_deposit" in payload:

            payload["is_cash"] = is_cash

            payload["is_bank"] = is_bank

            payload["is_patient_deposit"] = is_patient_deposit



        for field, value in payload.items():

            setattr(item, field, value)



        await self.repo.session.flush()

        await self.repo.session.refresh(item)

        return LedgerRead.model_validate(item)



    async def delete_ledger(self, ledger_id: str) -> LedgerRead:

        item = await self.repo.get_by_id(ledger_id)

        if not item or not item.is_active:

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger not found")

        item.is_active = False

        await self.repo.session.flush()

        await self.repo.session.refresh(item)

        return LedgerRead.model_validate(item)


