from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CashbookEntryRead(BaseModel):
    id: str
    voucher_id: str
    voucher_no: str
    voucher_date: date
    source_type: str
    source_id: str
    ledger_id: str
    ledger_code: str
    ledger_name: str
    patient_id: str | None = None
    patient_no: str | None = None
    patient_name: str | None = None
    narration: str | None = None
    debit_amount: Decimal
    credit_amount: Decimal
    running_balance: Decimal | None = None
    created_at: datetime


class CashbookLedgerStatementRead(BaseModel):
    ledger_id: str
    ledger_code: str
    ledger_name: str
    from_date: date | None = None
    to_date: date | None = None
    opening_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
    entries: list[CashbookEntryRead]


class CashbookPatientAccountRead(BaseModel):
    patient_id: str
    patient_no: str
    patient_name: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal
    deposit_balance: Decimal | None = None
    entries: list[CashbookEntryRead]


class CashbookDaybookRead(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    total_debit: Decimal
    total_credit: Decimal
    entries: list[CashbookEntryRead]


class CashbookQueryParams(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    limit: int = Field(default=500, ge=1, le=2000)
