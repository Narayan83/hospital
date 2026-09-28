from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cashbook import CashbookVoucher, CashbookVoucherLine
from app.repositories.cashbook import CashbookRepository
from app.repositories.ledger import LedgerRepository
from app.repositories.payment_mode import PaymentModeRepository
from app.services.bill_number import BillNumberService

INCOME_LEDGER_CODES = {
    "opd_bill": "OPD-RECEIPT",
    "ipd_bill": "IPD-RECEIPT",
}

PATIENT_ACCOUNT_LEDGER_CODE = "PATIENT-ACCOUNT"
PAT_DEPOSIT_LEDGER_CODE = "PAT-DEPOSIT"


class CashbookPostingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CashbookRepository(session)
        self.ledger_repo = LedgerRepository(session)
        self.payment_mode_repo = PaymentModeRepository(session)
        self.number_svc = BillNumberService(session)

    async def _require_ledger(self, code: str):
        ledger = await self.ledger_repo.get_by_code(code)
        if not ledger or not ledger.is_active:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Required ledger '{code}' is not configured",
            )
        return ledger

    async def _require_ledger_by_id(self, ledger_id: str):
        ledger = await self.ledger_repo.get_by_id(ledger_id)
        if not ledger or not ledger.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ledger not found",
            )
        return ledger

    async def get_patient_deposit_balance(self, patient_id: str) -> Decimal:
        deposit_ledger = await self._require_ledger(PAT_DEPOSIT_LEDGER_CODE)
        balance = await self.repo.sum_patient_ledger_balance(deposit_ledger.id, patient_id)
        return Decimal(str(balance))

    async def post_bill(
        self,
        *,
        source_type: str,
        source_id: str,
        bill_no: str,
        bill_date: date,
        patient_id: str,
        patient_no: str,
        payment_entries: list[tuple[str, Decimal]],
        gross_amount: Decimal,
        net_amount: Decimal,
        adjust_advance: Decimal = Decimal("0"),
        created_by_user_id: str | None = None,
    ) -> CashbookVoucher:
        if source_type not in INCOME_LEDGER_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported cashbook source type: {source_type}",
            )

        adjust = max(Decimal("0"), Decimal(str(adjust_advance or 0)))
        net = max(Decimal("0"), Decimal(str(net_amount or 0)))
        # Bill value credited to income = net payable + advance adjusted
        # (equals gross + admin - scheme when those fields are applied in billing).
        bill_value = net + adjust
        if bill_value <= 0 and Decimal(str(gross_amount or 0)) > 0:
            bill_value = max(Decimal("0"), Decimal(str(gross_amount or 0)))

        if adjust > 0:
            available = await self.get_patient_deposit_balance(patient_id)
            if adjust > available + Decimal("0.01"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient patient advance balance. Available: {available:.2f}, "
                        f"requested adjustment: {adjust:.2f}"
                    ),
                )

        await self.repo.deactivate_by_source(source_type, source_id)

        income_ledger = await self._require_ledger(INCOME_LEDGER_CODES[source_type])
        patient_account_ledger = await self._require_ledger(PATIENT_ACCOUNT_LEDGER_CODE)

        bill_label = "OPD" if source_type == "opd_bill" else "IPD"
        narration = f"{bill_label} Bill {bill_no}"
        if adjust > 0:
            narration = f"{narration} (Advance adjusted {adjust:.2f})"

        voucher = CashbookVoucher(
            voucher_no=bill_no,
            voucher_date=bill_date,
            source_type=source_type,
            source_id=source_id,
            patient_id=patient_id,
            patient_no=patient_no,
            narration=narration,
            created_by_user_id=created_by_user_id,
            is_active=True,
            lines=[],
        )
        self.session.add(voucher)
        await self.session.flush()

        sort_order = 0
        for mode_id, amount in payment_entries:
            mode = await self.payment_mode_repo.get_by_id(mode_id)
            if not mode or not mode.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payment mode not found: {mode_id}",
                )
            if not mode.ledger_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Payment mode '{mode.name}' has no ledger mapped. "
                        "Configure the ledger in Payment Mode Creation."
                    ),
                )
            voucher.lines.append(
                CashbookVoucherLine(
                    ledger_id=mode.ledger_id,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            sort_order += 1

        if adjust > 0:
            deposit_ledger = await self._require_ledger(PAT_DEPOSIT_LEDGER_CODE)
            voucher.lines.append(
                CashbookVoucherLine(
                    ledger_id=deposit_ledger.id,
                    debit_amount=adjust,
                    credit_amount=Decimal("0"),
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            sort_order += 1

        voucher.lines.append(
            CashbookVoucherLine(
                ledger_id=income_ledger.id,
                debit_amount=Decimal("0"),
                credit_amount=bill_value,
                sort_order=sort_order,
                is_active=True,
            )
        )
        sort_order += 1

        voucher.lines.append(
            CashbookVoucherLine(
                ledger_id=patient_account_ledger.id,
                debit_amount=Decimal("0"),
                credit_amount=bill_value,
                sort_order=sort_order,
                is_active=True,
            )
        )
        sort_order += 1

        for _mode_id, amount in payment_entries:
            voucher.lines.append(
                CashbookVoucherLine(
                    ledger_id=patient_account_ledger.id,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            sort_order += 1

        if adjust > 0:
            voucher.lines.append(
                CashbookVoucherLine(
                    ledger_id=patient_account_ledger.id,
                    debit_amount=adjust,
                    credit_amount=Decimal("0"),
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            sort_order += 1

        await self.session.flush()
        return voucher

    async def repost_bill(
        self,
        *,
        source_type: str,
        source_id: str,
        bill_no: str,
        bill_date: date,
        patient_id: str,
        patient_no: str,
        payment_entries: list[tuple[str, Decimal]],
        gross_amount: Decimal,
        net_amount: Decimal,
        adjust_advance: Decimal = Decimal("0"),
        created_by_user_id: str | None = None,
    ) -> CashbookVoucher:
        return await self.post_bill(
            source_type=source_type,
            source_id=source_id,
            bill_no=bill_no,
            bill_date=bill_date,
            patient_id=patient_id,
            patient_no=patient_no,
            payment_entries=payment_entries,
            gross_amount=gross_amount,
            net_amount=net_amount,
            adjust_advance=adjust_advance,
            created_by_user_id=created_by_user_id,
        )

    async def post_advance_collection(
        self,
        *,
        voucher_id: str,
        voucher_no: str,
        voucher_date: date,
        patient_id: str,
        patient_no: str,
        payment_mode_id: str,
        amount: Decimal,
        narration: str | None,
        created_by_user_id: str | None = None,
    ) -> CashbookVoucher:
        amount = Decimal(str(amount))
        mode = await self.payment_mode_repo.get_by_id(payment_mode_id)
        if not mode or not mode.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment mode not found")
        if not mode.ledger_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment mode '{mode.name}' has no ledger mapped",
            )

        deposit_ledger = await self._require_ledger(PAT_DEPOSIT_LEDGER_CODE)
        voucher = CashbookVoucher(
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            source_type="advance_collection",
            source_id=voucher_id,
            patient_id=patient_id,
            patient_no=patient_no,
            narration=narration or f"Advance collection — {patient_no}",
            created_by_user_id=created_by_user_id,
            is_active=True,
            lines=[
                CashbookVoucherLine(
                    ledger_id=mode.ledger_id,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                    sort_order=0,
                    is_active=True,
                ),
                CashbookVoucherLine(
                    ledger_id=deposit_ledger.id,
                    debit_amount=Decimal("0"),
                    credit_amount=amount,
                    sort_order=1,
                    is_active=True,
                ),
            ],
        )
        self.session.add(voucher)
        await self.session.flush()
        return voucher

    async def post_payment_voucher(
        self,
        *,
        voucher_id: str,
        voucher_no: str,
        voucher_date: date,
        ledger_id: str,
        counter_ledger_id: str,
        patient_id: str | None,
        patient_no: str | None,
        amount: Decimal,
        entry_type: str,
        narration: str | None,
        created_by_user_id: str | None = None,
    ) -> CashbookVoucher:
        amount = Decimal(str(amount))
        ledger = await self._require_ledger_by_id(ledger_id)
        counter = await self._require_ledger_by_id(counter_ledger_id)
        entry = (entry_type or "receipt").strip().lower()

        if ledger.is_patient_deposit and not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient is required when using a patient deposit ledger",
            )

        if entry == "receipt":
            debit_ledger_id = counter.id
            credit_ledger_id = ledger.id
        else:
            debit_ledger_id = ledger.id
            credit_ledger_id = counter.id

        voucher = CashbookVoucher(
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            source_type="payment_voucher",
            source_id=voucher_id,
            patient_id=patient_id,
            patient_no=patient_no,
            narration=narration or f"Payment voucher {voucher_no}",
            created_by_user_id=created_by_user_id,
            is_active=True,
            lines=[
                CashbookVoucherLine(
                    ledger_id=debit_ledger_id,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                    sort_order=0,
                    is_active=True,
                ),
                CashbookVoucherLine(
                    ledger_id=credit_ledger_id,
                    debit_amount=Decimal("0"),
                    credit_amount=amount,
                    sort_order=1,
                    is_active=True,
                ),
            ],
        )
        self.session.add(voucher)
        await self.session.flush()
        return voucher

    async def post_contra_entry(
        self,
        *,
        voucher_id: str,
        voucher_no: str,
        voucher_date: date,
        from_ledger_id: str,
        to_ledger_id: str,
        amount: Decimal,
        narration: str | None,
        created_by_user_id: str | None = None,
    ) -> CashbookVoucher:
        amount = Decimal(str(amount))
        from_ledger = await self._require_ledger_by_id(from_ledger_id)
        to_ledger = await self._require_ledger_by_id(to_ledger_id)
        if from_ledger.id == to_ledger.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="From and To ledgers must be different",
            )

        voucher = CashbookVoucher(
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            source_type="contra_entry",
            source_id=voucher_id,
            patient_id=None,
            patient_no=None,
            narration=narration or f"Contra {from_ledger.code} → {to_ledger.code}",
            created_by_user_id=created_by_user_id,
            is_active=True,
            lines=[
                CashbookVoucherLine(
                    ledger_id=to_ledger.id,
                    debit_amount=amount,
                    credit_amount=Decimal("0"),
                    sort_order=0,
                    is_active=True,
                ),
                CashbookVoucherLine(
                    ledger_id=from_ledger.id,
                    debit_amount=Decimal("0"),
                    credit_amount=amount,
                    sort_order=1,
                    is_active=True,
                ),
            ],
        )
        self.session.add(voucher)
        await self.session.flush()
        return voucher
