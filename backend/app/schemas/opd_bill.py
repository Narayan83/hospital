from datetime import date, datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.schemas.bill_payment import BillPaymentCreate, BillPaymentRead


class OpdBillLineCreate(BaseModel):
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


VisitCategory = Literal["opd", "reference", "appointment", "online_booking"]
TokenSession = Literal["morning", "evening"]

SCHEDULED_VISIT_CATEGORIES = frozenset({"appointment", "online_booking"})


class OpdBillCreate(BaseModel):
    patient_id: str
    doctor_id: str | None = None
    payment_mode_id: str | None = None
    payments: list[BillPaymentCreate] = Field(default_factory=list)
    department_id: str | None = None
    is_cash: bool = True
    scheme: str | None = Field(None, max_length=100)
    admin_charges: Decimal = Field(default=Decimal("0"), ge=0)
    scheme_discount: Decimal = Field(default=Decimal("0"), ge=0)
    sanctioned_scheme_amount: Decimal = Field(default=Decimal("0"), ge=0)
    adjust_advance: Decimal = Field(default=Decimal("0"), ge=0)
    remarks: str | None = None
    bill_date: date | None = None
    visit_category: VisitCategory = "opd"
    token_session: TokenSession | None = None
    appointment_date: date | None = None
    lines: list[OpdBillLineCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_visit_token_fields(self) -> "OpdBillCreate":
        if not self.doctor_id:
            raise ValueError("Doctor is required")
        if not self.token_session:
            raise ValueError("Session (morning/evening) is required")
        if self.visit_category in SCHEDULED_VISIT_CATEGORIES:
            if not self.appointment_date:
                raise ValueError("Booking date is required for appointment and online booking visits")
        return self


class OpdBillUpdate(BaseModel):
    doctor_id: str | None = None
    payment_mode_id: str | None = None
    payments: list[BillPaymentCreate] = Field(default_factory=list)
    department_id: str | None = None
    scheme: str | None = Field(None, max_length=100)
    admin_charges: Decimal = Field(default=Decimal("0"), ge=0)
    scheme_discount: Decimal = Field(default=Decimal("0"), ge=0)
    sanctioned_scheme_amount: Decimal = Field(default=Decimal("0"), ge=0)
    adjust_advance: Decimal = Field(default=Decimal("0"), ge=0)
    remarks: str | None = None
    visit_category: VisitCategory | None = None
    token_session: TokenSession | None = None
    appointment_date: date | None = None
    lines: list[OpdBillLineCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lines(self) -> "OpdBillUpdate":
        if not self.lines:
            raise ValueError("At least one service line is required")
        if not self.doctor_id:
            raise ValueError("Doctor is required")
        if not self.token_session:
            raise ValueError("Session (morning/evening) is required")
        if self.visit_category in SCHEDULED_VISIT_CATEGORIES and not self.appointment_date:
            raise ValueError("Booking date is required for appointment and online booking visits")
        return self


class OpdBillLineRead(ORMModel):
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


class OpdBillSummaryRead(BaseModel):
    id: str
    bill_no: str
    bill_date: date
    doctor_name: str | None = None
    department_name: str | None = None
    net_amount: Decimal
    gross_amount: Decimal
    token_number: int | None = None
    token_session: str | None = None
    visit_category: str
    payment_mode_name: str | None = None
    created_at: datetime

    @field_validator("net_amount", "gross_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class OpdBillRead(ORMModel):
    id: str
    bill_no: str
    bill_date: date
    patient_id: str
    patient_no: str | None = None
    patient_name: str | None = None
    doctor_id: str | None
    doctor_name: str | None = None
    payment_mode_id: str | None
    payment_mode_name: str | None = None
    payments: list[BillPaymentRead] = Field(default_factory=list)
    department_id: str | None
    department_name: str | None = None
    is_cash: bool
    scheme: str | None
    admin_charges: Decimal
    scheme_discount: Decimal
    sanctioned_scheme_amount: Decimal
    adjust_advance: Decimal
    gross_amount: Decimal
    net_amount: Decimal
    remarks: str | None
    visit_category: str
    token_number: int | None = None
    token_session: str | None = None
    appointment_date: date | None = None
    status: str
    is_active: bool
    lines: list[OpdBillLineRead] = Field(default_factory=list)
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


class BillingServiceCatalogItem(BaseModel):
    id: str
    code: str
    name: str
    rate: Decimal
    service_charge: Decimal
    is_sharing: bool = False
    doctor_id: str | None = None
    doctor_name: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    sub_category_id: str | None = None
    sub_category_name: str | None = None
    is_renewal: bool = False
    renewal_days: int | None = None

    @field_validator("rate", "service_charge", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value
