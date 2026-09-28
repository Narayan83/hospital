from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class UserCashTransactionRow(BaseModel):
    bill_no: str
    patient_no: str
    patient_name: str
    amount: Decimal = Field(..., decimal_places=2)
    bill_date: date | None = None
    is_debit: bool = False


class UserCashTransactionPaymentGroup(BaseModel):
    payment_mode_name: str
    rows: list[UserCashTransactionRow]
    subtotal: Decimal = Field(..., decimal_places=2)


class UserCashTransactionBillTypeGroup(BaseModel):
    bill_type: str
    payment_groups: list[UserCashTransactionPaymentGroup]
    grand_total: Decimal = Field(..., decimal_places=2)
    is_debit: bool = False


class UserCashDayUserSummary(BaseModel):
    user_id: str
    user_name: str
    bill_type_totals: dict[str, Decimal] = Field(default_factory=dict)
    payment_mode_totals: dict[str, Decimal] = Field(default_factory=dict)
    day_total: Decimal = Field(..., decimal_places=2)


class UserCashDayGroup(BaseModel):
    bill_date: date
    users: list[UserCashDayUserSummary]
    day_total: Decimal = Field(..., decimal_places=2)


class UserCashTransactionReportRead(BaseModel):
    user_id: str | None = None
    user_name: str
    from_date: date | None
    to_date: date | None
    report_type: str = "detail"
    payment_mode_label: str = "All Modes"
    bill_type_groups: list[UserCashTransactionBillTypeGroup] = Field(default_factory=list)
    day_groups: list[UserCashDayGroup] = Field(default_factory=list)
    bill_collection_total: Decimal = Field(Decimal("0"), decimal_places=2)
    advance_collection_total: Decimal = Field(Decimal("0"), decimal_places=2)
    payment_debit_total: Decimal = Field(Decimal("0"), decimal_places=2)
    overall_grand_total: Decimal = Field(..., decimal_places=2)
