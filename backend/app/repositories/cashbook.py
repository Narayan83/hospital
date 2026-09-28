from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cashbook import CashbookVoucher, CashbookVoucherLine
from app.repositories.base import BaseRepository


class CashbookRepository(BaseRepository[CashbookVoucher]):
    model = CashbookVoucher

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_with_lines(self, voucher_id: str) -> CashbookVoucher | None:
        result = await self.session.execute(
            select(CashbookVoucher)
            .options(
                selectinload(CashbookVoucher.lines).selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucher.id == voucher_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_voucher_no(self, voucher_no: str) -> CashbookVoucher | None:
        result = await self.session.execute(
            select(CashbookVoucher)
            .options(
                selectinload(CashbookVoucher.lines).selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucher.voucher_no.ilike(voucher_no.strip()))
            .where(CashbookVoucher.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_active_by_source_type(
        self,
        source_type: str,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 200,
    ) -> list[CashbookVoucher]:
        stmt = (
            select(CashbookVoucher)
            .options(
                selectinload(CashbookVoucher.lines).selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucher.source_type == source_type)
            .where(CashbookVoucher.is_active.is_(True))
        )
        if patient_id:
            stmt = stmt.where(CashbookVoucher.patient_id == patient_id)
        if patient_no and patient_no.strip():
            stmt = stmt.where(CashbookVoucher.patient_no.ilike(patient_no.strip()))
        if from_date:
            stmt = stmt.where(CashbookVoucher.voucher_date >= from_date)
        if to_date:
            stmt = stmt.where(CashbookVoucher.voucher_date <= to_date)
        stmt = stmt.order_by(
            CashbookVoucher.voucher_date.desc(),
            CashbookVoucher.created_at.desc(),
        ).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_by_source_types(
        self,
        source_types: Sequence[str],
        *,
        user_ids: list[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[CashbookVoucher]:
        stmt = (
            select(CashbookVoucher)
            .options(
                selectinload(CashbookVoucher.lines).selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucher.source_type.in_(list(source_types)))
            .where(CashbookVoucher.is_active.is_(True))
        )
        if user_ids is not None:
            stmt = stmt.where(CashbookVoucher.created_by_user_id.in_(user_ids))
        if from_date:
            stmt = stmt.where(CashbookVoucher.voucher_date >= from_date)
        if to_date:
            stmt = stmt.where(CashbookVoucher.voucher_date <= to_date)
        stmt = stmt.order_by(CashbookVoucher.voucher_date, CashbookVoucher.voucher_no)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_source(self, source_type: str, source_id: str) -> CashbookVoucher | None:
        result = await self.session.execute(
            select(CashbookVoucher)
            .options(selectinload(CashbookVoucher.lines).selectinload(CashbookVoucherLine.ledger))
            .where(CashbookVoucher.source_type == source_type)
            .where(CashbookVoucher.source_id == source_id)
            .where(CashbookVoucher.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def deactivate_by_source(self, source_type: str, source_id: str) -> None:
        result = await self.session.execute(
            select(CashbookVoucher)
            .options(selectinload(CashbookVoucher.lines))
            .where(CashbookVoucher.source_type == source_type)
            .where(CashbookVoucher.source_id == source_id)
            .where(CashbookVoucher.is_active.is_(True))
        )
        for voucher in result.scalars().all():
            voucher.is_active = False
            for line in voucher.lines:
                line.is_active = False

    async def list_ledger_lines(
        self,
        ledger_id: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 500,
    ) -> list[tuple[CashbookVoucherLine, CashbookVoucher]]:
        stmt = (
            select(CashbookVoucherLine, CashbookVoucher)
            .join(CashbookVoucher, CashbookVoucherLine.voucher_id == CashbookVoucher.id)
            .options(
                selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucherLine.ledger_id == ledger_id)
            .where(CashbookVoucherLine.is_active.is_(True))
            .where(CashbookVoucher.is_active.is_(True))
        )
        if from_date:
            stmt = stmt.where(CashbookVoucher.voucher_date >= from_date)
        if to_date:
            stmt = stmt.where(CashbookVoucher.voucher_date <= to_date)
        stmt = stmt.order_by(CashbookVoucher.voucher_date, CashbookVoucher.created_at, CashbookVoucherLine.sort_order)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.all())

    async def list_patient_voucher_lines(
        self,
        patient_id: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 500,
    ) -> list[tuple[CashbookVoucherLine, CashbookVoucher]]:
        stmt = (
            select(CashbookVoucherLine, CashbookVoucher)
            .join(CashbookVoucher, CashbookVoucherLine.voucher_id == CashbookVoucher.id)
            .options(
                selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucher.patient_id == patient_id)
            .where(CashbookVoucherLine.is_active.is_(True))
            .where(CashbookVoucher.is_active.is_(True))
        )
        if from_date:
            stmt = stmt.where(CashbookVoucher.voucher_date >= from_date)
        if to_date:
            stmt = stmt.where(CashbookVoucher.voucher_date <= to_date)
        stmt = stmt.order_by(CashbookVoucher.voucher_date, CashbookVoucher.created_at, CashbookVoucherLine.sort_order)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.all())

    async def sum_ledger_before(
        self,
        ledger_id: str,
        before_date: date | None,
    ) -> tuple[float, float]:
        stmt = (
            select(CashbookVoucherLine, CashbookVoucher)
            .join(CashbookVoucher, CashbookVoucherLine.voucher_id == CashbookVoucher.id)
            .where(CashbookVoucherLine.ledger_id == ledger_id)
            .where(CashbookVoucherLine.is_active.is_(True))
            .where(CashbookVoucher.is_active.is_(True))
        )
        if before_date:
            stmt = stmt.where(CashbookVoucher.voucher_date < before_date)
        result = await self.session.execute(stmt)
        total_debit = 0.0
        total_credit = 0.0
        for line, _voucher in result.all():
            total_debit += float(line.debit_amount or 0)
            total_credit += float(line.credit_amount or 0)
        return total_debit, total_credit

    async def sum_patient_ledger_balance(
        self,
        ledger_id: str,
        patient_id: str,
        *,
        before_date: date | None = None,
    ) -> float:
        stmt = (
            select(CashbookVoucherLine, CashbookVoucher)
            .join(CashbookVoucher, CashbookVoucherLine.voucher_id == CashbookVoucher.id)
            .where(CashbookVoucherLine.ledger_id == ledger_id)
            .where(CashbookVoucher.patient_id == patient_id)
            .where(CashbookVoucherLine.is_active.is_(True))
            .where(CashbookVoucher.is_active.is_(True))
        )
        if before_date:
            stmt = stmt.where(CashbookVoucher.voucher_date < before_date)
        result = await self.session.execute(stmt)
        total_debit = 0.0
        total_credit = 0.0
        for line, _voucher in result.all():
            total_debit += float(line.debit_amount or 0)
            total_credit += float(line.credit_amount or 0)
        return total_credit - total_debit

    async def list_daybook_lines(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 2000,
    ) -> list[tuple[CashbookVoucherLine, CashbookVoucher]]:
        stmt = (
            select(CashbookVoucherLine, CashbookVoucher)
            .join(CashbookVoucher, CashbookVoucherLine.voucher_id == CashbookVoucher.id)
            .options(
                selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucherLine.is_active.is_(True))
            .where(CashbookVoucher.is_active.is_(True))
        )
        if from_date:
            stmt = stmt.where(CashbookVoucher.voucher_date >= from_date)
        if to_date:
            stmt = stmt.where(CashbookVoucher.voucher_date <= to_date)
        stmt = stmt.order_by(
            CashbookVoucher.voucher_date,
            CashbookVoucher.created_at,
            CashbookVoucherLine.sort_order,
        )
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.all())

    async def list_cash_bank_lines(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 2000,
    ) -> list[tuple[CashbookVoucherLine, CashbookVoucher]]:
        from app.models.ledger import Ledger

        stmt = (
            select(CashbookVoucherLine, CashbookVoucher)
            .join(CashbookVoucher, CashbookVoucherLine.voucher_id == CashbookVoucher.id)
            .join(Ledger, CashbookVoucherLine.ledger_id == Ledger.id)
            .options(
                selectinload(CashbookVoucherLine.ledger),
                selectinload(CashbookVoucher.patient),
            )
            .where(CashbookVoucherLine.is_active.is_(True))
            .where(CashbookVoucher.is_active.is_(True))
            .where((Ledger.is_cash.is_(True)) | (Ledger.is_bank.is_(True)))
        )
        if from_date:
            stmt = stmt.where(CashbookVoucher.voucher_date >= from_date)
        if to_date:
            stmt = stmt.where(CashbookVoucher.voucher_date <= to_date)
        stmt = stmt.order_by(
            CashbookVoucher.voucher_date,
            CashbookVoucher.created_at,
            CashbookVoucherLine.sort_order,
        )
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.all())
