from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class AdvanceCollectionCreate(BaseModel):
    patient_id: str
    voucher_date: date | None = None
    payment_mode_id: str
    amount: Decimal = Field(..., gt=Decimal("0"))
    narration: str | None = None


class AdvanceCollectionUpdate(BaseModel):
    voucher_date: date | None = None
    payment_mode_id: str | None = None
    amount: Decimal | None = Field(None, gt=Decimal("0"))
    narration: str | None = None


class AdvanceCollectionRead(ORMModel):
    id: str
    voucher_no: str
    voucher_date: date
    source_id: str
    patient_id: str | None = None
    patient_no: str | None = None
    patient_name: str | None = None
    amount: Decimal
    payment_mode_id: str | None = None
    payment_mode_code: str | None = None
    payment_mode_name: str | None = None
    narration: str | None = None


class PaymentVoucherCreate(BaseModel):
    voucher_date: date | None = None
    ledger_id: str
    counter_ledger_id: str
    patient_id: str | None = None
    amount: Decimal = Field(..., gt=Decimal("0"))
    entry_type: Literal["receipt", "payment"] = "receipt"
    narration: str | None = None

    @model_validator(mode="after")
    def _validate_patient_for_deposit(self):
        return self


class ContraEntryCreate(BaseModel):
    voucher_date: date | None = None
    from_ledger_id: str
    to_ledger_id: str
    amount: Decimal = Field(..., gt=Decimal("0"))
    narration: str | None = None

    @model_validator(mode="after")
    def _validate_ledgers(self):
        if self.from_ledger_id == self.to_ledger_id:
            raise ValueError("From and To ledgers must be different")
        return self


class AccountingVoucherRead(ORMModel):
    id: str
    voucher_no: str
    voucher_date: date
    source_type: str
    source_id: str
    patient_id: str | None = None
    patient_no: str | None = None
    narration: str | None = None


class PatientDepositBalanceRead(BaseModel):
    patient_id: str
    patient_no: str
    patient_name: str | None = None
    balance: Decimal
