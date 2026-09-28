from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.opd_bill import BillingServiceCatalogItem


class PathologyBillLineCreate(BaseModel):
    service_id: str
    quantity: int = Field(default=1, ge=1)
    rate: Decimal | None = Field(None, ge=0)
    service_name: str | None = Field(None, max_length=200)
    line_source: str = Field(default="manual", max_length=20)
    package_id: str | None = None
    panel_service_id: str | None = None
    panel_name: str | None = Field(None, max_length=200)
    is_panel_parent: bool = False
    reference_range_text: str | None = Field(None, max_length=250)
    result_value: str | None = Field(None, max_length=250)
    is_abnormal: bool = False


class PathologyBillCreate(BaseModel):
    patient_id: str
    doctor_id: str | None = None
    referring_doctor: str | None = Field(None, max_length=150)
    payment_mode_id: str | None = None
    department_id: str | None = None
    is_cash: bool = True
    scheme: str | None = Field(None, max_length=100)
    admin_charges: Decimal = Field(default=Decimal("0"), ge=0)
    scheme_discount: Decimal = Field(default=Decimal("0"), ge=0)
    adjust_advance: Decimal = Field(default=Decimal("0"), ge=0)
    remarks: str | None = None
    bill_date: date | None = None
    sample_date: date | None = None
    sample_no: str | None = Field(None, max_length=30)
    lines: list[PathologyBillLineCreate] = Field(default_factory=list)


class PathologyBillUpdate(BaseModel):
    doctor_id: str | None = None
    referring_doctor: str | None = Field(None, max_length=150)
    payment_mode_id: str | None = None
    department_id: str | None = None
    is_cash: bool | None = None
    scheme: str | None = Field(None, max_length=100)
    admin_charges: Decimal = Field(default=Decimal("0"), ge=0)
    scheme_discount: Decimal = Field(default=Decimal("0"), ge=0)
    adjust_advance: Decimal = Field(default=Decimal("0"), ge=0)
    remarks: str | None = None
    sample_date: date | None = None
    sample_no: str | None = Field(None, max_length=30)
    lines: list[PathologyBillLineCreate] = Field(default_factory=list)

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, value: list[PathologyBillLineCreate]) -> list[PathologyBillLineCreate]:
        if not value:
            raise ValueError("At least one test/service line is required")
        return value


class PathologyBillLineRead(ORMModel):
    id: str
    service_id: str | None
    service_code: str
    service_name: str
    category_name: str | None
    sub_category_name: str | None
    rate: Decimal
    quantity: int
    amount: Decimal
    line_source: str
    package_id: str | None
    panel_service_id: str | None = None
    panel_name: str | None = None
    is_panel_parent: bool = False
    reference_range_text: str | None = None
    result_value: str | None = None
    is_abnormal: bool = False
    sort_order: int

    @field_validator("rate", "amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class PathologyBillSummaryRead(BaseModel):
    id: str
    bill_no: str
    bill_date: date
    doctor_name: str | None = None
    department_name: str | None = None
    net_amount: Decimal
    gross_amount: Decimal
    order_status: str | None = None
    sample_no: str | None = None
    sample_date: date | None = None
    payment_mode_name: str | None = None
    created_at: datetime

    @field_validator("net_amount", "gross_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


class PathologyBillRead(ORMModel):
    id: str
    bill_no: str
    bill_date: date
    patient_id: str
    patient_no: str | None = None
    patient_name: str | None = None
    patient_gender: str | None = None
    patient_age: str | None = None
    doctor_id: str | None
    doctor_name: str | None = None
    doctor_qualification: str | None = None
    referring_doctor: str | None = None
    payment_mode_id: str | None
    payment_mode_name: str | None = None
    department_id: str | None
    department_name: str | None = None
    is_cash: bool
    scheme: str | None
    admin_charges: Decimal
    scheme_discount: Decimal
    adjust_advance: Decimal
    gross_amount: Decimal
    net_amount: Decimal
    remarks: str | None
    status: str
    is_active: bool
    order_status: str | None = None
    sample_no: str | None = None
    sample_date: date | None = None
    lines: list[PathologyBillLineRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "admin_charges",
        "scheme_discount",
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


class PathologyBillExpandLine(BaseModel):
    """One row on the pathology bill grid (panel parent + sub-test)."""

    service_id: str
    service_code: str
    service_name: str
    panel_service_id: str | None = None
    panel_code: str | None = None
    panel_name: str | None = None
    rate: Decimal
    quantity: int = 1
    amount: Decimal
    reference_range_text: str | None = None
    unit_name: str | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    is_panel_parent: bool = False

    @field_validator("rate", "amount", "min_value", "max_value", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value


__all__ = [
    "BillingServiceCatalogItem",
    "PathologyBillExpandLine",
    "PathologyBillCreate",
    "PathologyBillLineCreate",
    "PathologyBillLineRead",
    "PathologyBillRead",
    "PathologyBillSummaryRead",
    "PathologyBillUpdate",
]
