from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import Ledger
from app.repositories.base import BaseRepository


class LedgerRepository(BaseRepository[Ledger]):
    model = Ledger

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_active(self) -> list[Ledger]:
        result = await self.session.execute(
            select(Ledger)
            .where(Ledger.is_active.is_(True))
            .order_by(Ledger.sort_order, Ledger.name)
        )
        return list(result.scalars().all())

    async def list_by_flags(
        self,
        *,
        is_cash: bool | None = None,
        is_bank: bool | None = None,
        is_patient_deposit: bool | None = None,
        ledger_type: str | None = None,
    ) -> list[Ledger]:
        stmt = select(Ledger).where(Ledger.is_active.is_(True))
        if is_cash is not None:
            stmt = stmt.where(Ledger.is_cash.is_(is_cash))
        if is_bank is not None:
            stmt = stmt.where(Ledger.is_bank.is_(is_bank))
        if is_patient_deposit is not None:
            stmt = stmt.where(Ledger.is_patient_deposit.is_(is_patient_deposit))
        if ledger_type:
            stmt = stmt.where(Ledger.ledger_type == ledger_type.upper())
        result = await self.session.execute(
            stmt.order_by(Ledger.sort_order, Ledger.name)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Ledger | None:
        result = await self.session.execute(
            select(Ledger).where(Ledger.code == code.upper())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, ledger_id: str) -> Ledger | None:
        result = await self.session.execute(
            select(Ledger).where(Ledger.id == ledger_id)
        )
        return result.scalar_one_or_none()
