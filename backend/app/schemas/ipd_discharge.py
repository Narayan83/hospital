from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.schemas.bill_payment import BillPaymentCreate, BillPaymentRead


class IpdDischargeLineCreate(BaseModel):
    service_id: str
    quantity: int = Field(default=1, ge=1)
    rate: Decimal | None = Field(None, ge=0)
    service_name: str | None = Field(None, max_length=200)
    line_source: str = Field(default="manual", max_length=20)
    package_id: str | None = None
    original_rate: Decimal | None = Field(None, ge=0)
    hospital_amount: Decimal | None = Field(None, ge=0)
    doctor_amount: Decimal | None = Field(None, ge=0)
    sharing_doctor_id: str | None = None


class IpdDischargeCreate(BaseModel):
    patient_id: str
    admission_id: str | None = None
    ward_id: str | None = None
    bed_no: str | None = Field(None, max_length=30)
    doctor_id: str | None = None
    admission_date: date | None = None
    discharge_date: date | None = None
    payment_mode_id: str | None = None
    payments: list[BillPaymentCreate] = Field(default_factory=list)
    is_cash: bool = True
    scheme: str | None = Field(None, max_length=100)
    admin_charges: Decimal = Field(default=Decimal("0"), ge=0)
    scheme_discount: Decimal = Field(default=Decimal("0"), ge=0)
    sanctioned_scheme_amount: Decimal = Field(default=Decimal("0"), ge=0)
    adjust_advance: Decimal = Field(default=Decimal("0"), ge=0)
    hide_advance_on_bill: bool = False
    remarks: str | None = None
    lines: list[IpdDischargeLineCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lines(self) -> "IpdDischargeCreate":
        if not self.lines:
            raise ValueError("At least one service line is required")
        return self


class IpdDischargeUpdate(BaseModel):
    discharge_date: date | None = None
    ward_id: str | None = None
    bed_no: str | None = Field(None, max_length=30)
    payment_mode_id: str | None = None
    payments: list[BillPaymentCreate] = Field(default_factory=list)
    is_cash: bool = True
    scheme: str | None = Field(None, max_length=100)
    admin_charges: Decimal = Field(default=Decimal("0"), ge=0)
    scheme_discount: Decimal = Field(default=Decimal("0"), ge=0)
    sanctioned_scheme_amount: Decimal = Field(default=Decimal("0"), ge=0)
    adjust_advance: Decimal = Field(default=Decimal("0"), ge=0)
    hide_advance_on_bill: bool = False
    remarks: str | None = None
    lines: list[IpdDischargeLineCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lines(self) -> "IpdDischargeUpdate":
        if not self.lines:
            raise ValueError("At least one service line is required")
        return self


class IpdDischargeLineRead(ORMModel):
    id: str
    service_id: str | None
    service_code: str
    service_name: str
    category_name: str | None
    sub_category_name: str | None
    rate: Decimal
    quantity: int
    amount: Decimal
    original_rate: Decimal | None = None
    hospital_amount: Decimal = Decimal("0")
    doctor_amount: Decimal = Decimal("0")
    sharing_doctor_id: str | None = None
    line_source: str
    package_id: str | None
    sort_order: int

    @field_validator("rate", "amount", "original_rate", "hospital_amount", "doctor_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class IpdDischargeSummaryRead(BaseModel):
    id: str
    bill_no: str
    bill_date: date
    admission_no: str | None = None
    doctor_name: str | None = None
    ward_name: str | None = None
    net_amount: Decimal
    gross_amount: Decimal
    discharge_date: date
    stay_days: int
    payment_mode_name: str | None = None
    created_at: datetime

    @field_validator("net_amount", "gross_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class IpdDischargeRead(ORMModel):
    id: str
    bill_no: str
    bill_date: date
    admission_id: str | None = None
    admission_no: str | None = None
    patient_id: str
    patient_no: str | None = None
    patient_name: str | None = None
    ward_id: str | None
    ward_name: str | None = None
    doctor_id: str | None
    doctor_name: str | None = None
    department_id: str | None
    department_name: str | None = None
    bed_no: str | None
    admission_date: date
    discharge_date: date
    stay_days: int
    payment_mode_id: str | None
    payment_mode_name: str | None = None
    payments: list[BillPaymentRead] = Field(default_factory=list)
    is_cash: bool
    scheme: str | None
    admin_charges: Decimal
    scheme_discount: Decimal
    sanctioned_scheme_amount: Decimal
    adjust_advance: Decimal
    hide_advance_on_bill: bool = False
    gross_amount: Decimal
    net_amount: Decimal
    remarks: str | None
    status: str
    is_active: bool
    lines: list[IpdDischargeLineRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "admin_charges",
        "scheme_discount",
        "sanctioned_scheme_amount",
        "adjust_advance",
        "gross_amount",
        "net_amount",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value
