from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cashbook import CashbookRepository
from app.repositories.ledger import LedgerRepository
from app.repositories.patient import PatientRepository
from app.schemas.cashbook import (
    CashbookDaybookRead,
    CashbookEntryRead,
    CashbookLedgerStatementRead,
    CashbookPatientAccountRead,
)
from app.services.cashbook_posting import CashbookPostingService
from app.services.ledger import signed_opening_balance


def _patient_name(patient) -> str | None:
    if not patient:
        return None
    parts = [patient.first_name, patient.middle_name, patient.last_name]
    return " ".join(p for p in parts if p)


def _line_to_entry(
    line,
    voucher,
    *,
    running_balance: Decimal | None = None,
) -> CashbookEntryRead:
    ledger = line.ledger
    patient = voucher.patient
    return CashbookEntryRead(
        id=line.id,
        voucher_id=voucher.id,
        voucher_no=voucher.voucher_no,
        voucher_date=voucher.voucher_date,
        source_type=voucher.source_type,
        source_id=voucher.source_id,
        ledger_id=line.ledger_id,
        ledger_code=ledger.code if ledger else "",
        ledger_name=ledger.name if ledger else "",
        patient_id=voucher.patient_id,
        patient_no=voucher.patient_no,
        patient_name=_patient_name(patient),
        narration=voucher.narration,
        debit_amount=Decimal(str(line.debit_amount or 0)),
        credit_amount=Decimal(str(line.credit_amount or 0)),
        running_balance=running_balance,
        created_at=line.created_at,
    )


class CashbookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CashbookRepository(session)
        self.ledger_repo = LedgerRepository(session)
        self.patient_repo = PatientRepository(session)

    async def ledger_statement(
        self,
        ledger_id: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 500,
    ) -> CashbookLedgerStatementRead:
        ledger = await self.ledger_repo.get_by_id(ledger_id)
        if not ledger or not ledger.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger not found")

        opening_debit, opening_credit = await self.repo.sum_ledger_before(ledger_id, from_date)
        opening_balance = (
            signed_opening_balance(ledger)
            + Decimal(str(opening_debit))
            - Decimal(str(opening_credit))
        )

        rows = await self.repo.list_ledger_lines(
            ledger_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

        entries: list[CashbookEntryRead] = []
        running = opening_balance
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for line, voucher in rows:
            debit = Decimal(str(line.debit_amount or 0))
            credit = Decimal(str(line.credit_amount or 0))
            total_debit += debit
            total_credit += credit
            running += debit - credit
            entries.append(_line_to_entry(line, voucher, running_balance=running))

        closing_balance = opening_balance + total_debit - total_credit
        return CashbookLedgerStatementRead(
            ledger_id=ledger.id,
            ledger_code=ledger.code,
            ledger_name=ledger.name,
            from_date=from_date,
            to_date=to_date,
            opening_balance=opening_balance,
            total_debit=total_debit,
            total_credit=total_credit,
            closing_balance=closing_balance,
            entries=entries,
        )

    async def patient_account(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 500,
    ) -> CashbookPatientAccountRead:
        resolved_patient_id = patient_id
        patient = None
        if not resolved_patient_id:
            if not patient_no or not patient_no.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="patient_id or patient_no is required",
                )
            patient = await self.patient_repo.get_by_patient_no(patient_no.strip())
            if not patient:
                items, _total = await self.patient_repo.advanced_search(
                    patient_no=patient_no.strip(),
                    page=1,
                    page_size=10,
                )
                patient = next(
                    (
                        item
                        for item in items
                        if item.patient_no.strip().upper() == patient_no.strip().upper()
                    ),
                    None,
                )
            if not patient or not patient.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
            resolved_patient_id = patient.id
        elif not patient:
            patient = await self.patient_repo.get_by_id(resolved_patient_id)
            if not patient or not patient.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        rows = await self.repo.list_patient_voucher_lines(
            resolved_patient_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

        entries: list[CashbookEntryRead] = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        running = Decimal("0")
        for line, voucher in rows:
            debit = Decimal(str(line.debit_amount or 0))
            credit = Decimal(str(line.credit_amount or 0))
            total_debit += debit
            total_credit += credit
            running += debit - credit
            entries.append(_line_to_entry(line, voucher, running_balance=running))

        return CashbookPatientAccountRead(
            patient_id=patient.id,
            patient_no=patient.patient_no,
            patient_name=_patient_name(patient),
            from_date=from_date,
            to_date=to_date,
            total_debit=total_debit,
            total_credit=total_credit,
            balance=total_debit - total_credit,
            deposit_balance=await CashbookPostingService(self.session).get_patient_deposit_balance(
                patient.id
            ),
            entries=entries,
        )

    async def daybook(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 2000,
    ) -> CashbookDaybookRead:
        rows = await self.repo.list_daybook_lines(
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
        entries: list[CashbookEntryRead] = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for line, voucher in rows:
            debit = Decimal(str(line.debit_amount or 0))
            credit = Decimal(str(line.credit_amount or 0))
            total_debit += debit
            total_credit += credit
            entries.append(_line_to_entry(line, voucher))
        return CashbookDaybookRead(
            from_date=from_date,
            to_date=to_date,
            total_debit=total_debit,
            total_credit=total_credit,
            entries=entries,
        )

    async def cash_book(
        self,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 2000,
    ) -> CashbookDaybookRead:
        rows = await self.repo.list_cash_bank_lines(
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
        entries: list[CashbookEntryRead] = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for line, voucher in rows:
            debit = Decimal(str(line.debit_amount or 0))
            credit = Decimal(str(line.credit_amount or 0))
            total_debit += debit
            total_credit += credit
            entries.append(_line_to_entry(line, voucher))
        return CashbookDaybookRead(
            from_date=from_date,
            to_date=to_date,
            total_debit=total_debit,
            total_credit=total_credit,
            entries=entries,
        )
