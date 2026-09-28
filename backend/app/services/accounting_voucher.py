from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.patient import PatientRepository
from app.schemas.accounting_voucher import (
    AccountingVoucherRead,
    AdvanceCollectionCreate,
    AdvanceCollectionRead,
    AdvanceCollectionUpdate,
    ContraEntryCreate,
    PatientDepositBalanceRead,
    PaymentVoucherCreate,
)
from app.services.bill_number import BillNumberService
from app.services.cashbook_posting import PAT_DEPOSIT_LEDGER_CODE, CashbookPostingService


def _patient_name(patient) -> str | None:
    if not patient:
        return None
    parts = [patient.first_name, patient.middle_name, patient.last_name]
    return " ".join(p for p in parts if p)


class AccountingVoucherService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.patient_repo = PatientRepository(session)
        self.posting = CashbookPostingService(session)
        self.number_svc = BillNumberService(session)

    async def _resolve_patient(self, patient_id: str):
        patient = await self.patient_repo.get_by_id(patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return patient

    def _to_read(self, voucher) -> AccountingVoucherRead:
        return AccountingVoucherRead.model_validate(voucher)

    def _advance_amount(self, voucher) -> Decimal:
        total = Decimal("0")
        for line in voucher.lines or []:
            if not line.is_active:
                continue
            credit = Decimal(str(line.credit_amount or 0))
            if credit > 0:
                total += credit
        if total > 0:
            return total
        for line in voucher.lines or []:
            if not line.is_active:
                continue
            debit = Decimal(str(line.debit_amount or 0))
            if debit > 0:
                return debit
        return Decimal("0")

    async def _payment_mode_for_voucher(self, voucher):
        for line in voucher.lines or []:
            if not line.is_active:
                continue
            if Decimal(str(line.debit_amount or 0)) > 0:
                return await self.posting.payment_mode_repo.get_by_ledger_id(line.ledger_id)
        return None

    async def _to_advance_read(self, voucher) -> AdvanceCollectionRead:
        mode = await self._payment_mode_for_voucher(voucher)
        patient = voucher.patient
        return AdvanceCollectionRead(
            id=voucher.id,
            voucher_no=voucher.voucher_no,
            voucher_date=voucher.voucher_date,
            source_id=voucher.source_id,
            patient_id=voucher.patient_id,
            patient_no=voucher.patient_no,
            patient_name=_patient_name(patient) if patient else None,
            amount=self._advance_amount(voucher),
            payment_mode_id=mode.id if mode else None,
            payment_mode_code=mode.code if mode else None,
            payment_mode_name=mode.name if mode else None,
            narration=voucher.narration,
        )

    async def _require_active_advance(self, voucher_id: str):
        voucher = await self.posting.repo.get_with_lines(voucher_id)
        if (
            not voucher
            or not voucher.is_active
            or voucher.source_type != "advance_collection"
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Advance voucher not found",
            )
        return voucher

    async def collect_advance(
        self,
        data: AdvanceCollectionCreate,
        *,
        created_by_user_id: str | None = None,
    ) -> AdvanceCollectionRead:
        patient = await self._resolve_patient(data.patient_id)
        voucher_date = data.voucher_date or date.today()
        voucher_id = str(uuid4())
        voucher_no = await self.number_svc.generate_accounting_voucher_no("advance", voucher_date)
        voucher = await self.posting.post_advance_collection(
            voucher_id=voucher_id,
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            patient_id=patient.id,
            patient_no=patient.patient_no,
            payment_mode_id=data.payment_mode_id,
            amount=Decimal(str(data.amount)),
            narration=data.narration,
            created_by_user_id=created_by_user_id,
        )
        voucher = await self.posting.repo.get_with_lines(voucher.id)
        return await self._to_advance_read(voucher)

    async def list_advances(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
        voucher_no: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 200,
    ) -> list[AdvanceCollectionRead]:
        if voucher_no and voucher_no.strip():
            voucher = await self.posting.repo.get_active_by_voucher_no(voucher_no.strip())
            if not voucher or voucher.source_type != "advance_collection":
                return []
            return [await self._to_advance_read(voucher)]

        if patient_no and patient_no.strip() and not patient_id:
            patient = await self.patient_repo.get_by_patient_no(patient_no.strip())
            if patient:
                patient_id = patient.id

        vouchers = await self.posting.repo.list_active_by_source_type(
            "advance_collection",
            patient_id=patient_id,
            patient_no=None if patient_id else patient_no,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
        return [await self._to_advance_read(v) for v in vouchers]

    async def get_advance(self, voucher_id: str) -> AdvanceCollectionRead:
        voucher = await self._require_active_advance(voucher_id)
        return await self._to_advance_read(voucher)

    async def get_advance_by_no(self, voucher_no: str) -> AdvanceCollectionRead:
        voucher = await self.posting.repo.get_active_by_voucher_no(voucher_no.strip())
        if not voucher or voucher.source_type != "advance_collection":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Advance voucher not found",
            )
        return await self._to_advance_read(voucher)

    async def update_advance(
        self,
        voucher_id: str,
        data: AdvanceCollectionUpdate,
        *,
        created_by_user_id: str | None = None,
    ) -> AdvanceCollectionRead:
        voucher = await self._require_active_advance(voucher_id)
        if not voucher.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Advance has no patient linked",
            )

        old_amount = self._advance_amount(voucher)
        new_amount = Decimal(str(data.amount)) if data.amount is not None else old_amount
        payment_mode_id = data.payment_mode_id
        if not payment_mode_id:
            mode = await self._payment_mode_for_voucher(voucher)
            if not mode:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment mode is required",
                )
            payment_mode_id = mode.id

        balance = await self.posting.get_patient_deposit_balance(voucher.patient_id)
        projected = balance - old_amount + new_amount
        if projected < Decimal("-0.01"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot reduce advance — patient balance would become negative "
                    f"(available after change: {projected:.2f})."
                ),
            )

        mode = await self.posting.payment_mode_repo.get_by_id(payment_mode_id)
        if not mode or not mode.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment mode not found",
            )
        if not mode.ledger_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment mode '{mode.name}' has no ledger mapped",
            )
        deposit_ledger = await self.posting._require_ledger(PAT_DEPOSIT_LEDGER_CODE)

        if data.voucher_date is not None:
            voucher.voucher_date = data.voucher_date
        if data.narration is not None:
            voucher.narration = (data.narration or "").strip() or None
        voucher.created_by_user_id = voucher.created_by_user_id or created_by_user_id

        for line in voucher.lines or []:
            if not line.is_active:
                continue
            if Decimal(str(line.credit_amount or 0)) > 0:
                line.ledger_id = deposit_ledger.id
                line.credit_amount = new_amount
                line.debit_amount = Decimal("0")
            elif Decimal(str(line.debit_amount or 0)) > 0:
                line.ledger_id = mode.ledger_id
                line.debit_amount = new_amount
                line.credit_amount = Decimal("0")

        await self.session.flush()
        voucher = await self.posting.repo.get_with_lines(voucher.id)
        return await self._to_advance_read(voucher)

    async def delete_advance(self, voucher_id: str) -> None:
        voucher = await self._require_active_advance(voucher_id)
        if not voucher.patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Advance has no patient linked",
            )
        amount = self._advance_amount(voucher)
        balance = await self.posting.get_patient_deposit_balance(voucher.patient_id)
        projected = balance - amount
        if projected < Decimal("-0.01"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete advance — patient has already used this amount "
                    f"(balance after delete would be {projected:.2f})."
                ),
            )
        await self.posting.repo.deactivate_by_source(
            "advance_collection", voucher.source_id
        )
        await self.session.flush()

    async def create_payment_voucher(
        self,
        data: PaymentVoucherCreate,
        *,
        created_by_user_id: str | None = None,
    ) -> AccountingVoucherRead:
        patient = None
        patient_no = None
        if data.patient_id:
            patient = await self._resolve_patient(data.patient_id)
            patient_no = patient.patient_no

        if data.entry_type == "payment" and data.patient_id:
            ledger = await self.posting._require_ledger_by_id(data.ledger_id)
            if ledger.is_patient_deposit:
                available = await self.posting.get_patient_deposit_balance(data.patient_id)
                if Decimal(str(data.amount)) > available + Decimal("0.01"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insufficient patient advance balance. Available: {available:.2f}",
                    )

        voucher_date = data.voucher_date or date.today()
        voucher_id = str(uuid4())
        voucher_no = await self.number_svc.generate_accounting_voucher_no("payment", voucher_date)
        voucher = await self.posting.post_payment_voucher(
            voucher_id=voucher_id,
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            ledger_id=data.ledger_id,
            counter_ledger_id=data.counter_ledger_id,
            patient_id=patient.id if patient else None,
            patient_no=patient_no,
            amount=Decimal(str(data.amount)),
            entry_type=data.entry_type,
            narration=data.narration,
            created_by_user_id=created_by_user_id,
        )
        return self._to_read(voucher)

    async def create_contra_entry(
        self,
        data: ContraEntryCreate,
        *,
        created_by_user_id: str | None = None,
    ) -> AccountingVoucherRead:
        voucher_date = data.voucher_date or date.today()
        voucher_id = str(uuid4())
        voucher_no = await self.number_svc.generate_accounting_voucher_no("contra", voucher_date)
        voucher = await self.posting.post_contra_entry(
            voucher_id=voucher_id,
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            from_ledger_id=data.from_ledger_id,
            to_ledger_id=data.to_ledger_id,
            amount=Decimal(str(data.amount)),
            narration=data.narration,
            created_by_user_id=created_by_user_id,
        )
        return self._to_read(voucher)

    async def patient_deposit_balance(
        self,
        *,
        patient_id: str | None = None,
        patient_no: str | None = None,
    ) -> PatientDepositBalanceRead:
        patient = None
        if patient_id:
            patient = await self._resolve_patient(patient_id)
        elif patient_no and patient_no.strip():
            patient = await self.patient_repo.get_by_patient_no(patient_no.strip())
            if not patient or not patient.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id or patient_no is required",
            )

        balance = await self.posting.get_patient_deposit_balance(patient.id)
        return PatientDepositBalanceRead(
            patient_id=patient.id,
            patient_no=patient.patient_no,
            patient_name=_patient_name(patient),
            balance=balance,
        )
