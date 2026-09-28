from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ShortBillTypeBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    menu_code: str = Field(..., min_length=1, max_length=50)
    default_service_id: str | None = None
    default_service_name: str | None = Field(None, max_length=200)
    default_rate: Decimal = Field(default=Decimal("0"), decimal_places=2)
    default_doctor_id: str | None = None
    bill_prefix: str = Field(default="SB", max_length=20)
    sort_order: int = 0
    is_active: bool = True


class ShortBillTypeCreate(ShortBillTypeBase):
    code: str | None = Field(None, max_length=30)
    menu_code: str | None = Field(None, max_length=50)


class ShortBillTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    default_service_id: str | None = None
    default_service_name: str | None = Field(None, max_length=200)
    default_rate: Decimal | None = Field(None, decimal_places=2)
    default_doctor_id: str | None = None
    bill_prefix: str | None = Field(None, max_length=20)
    sort_order: int | None = None
    is_active: bool | None = None


class ShortBillTypeRead(ShortBillTypeBase):
    id: str
    default_doctor_name: str | None = None

    model_config = {"from_attributes": True}


class ShortBillCreate(BaseModel):
    short_bill_type_id: str
    bill_date: date
    patient_id: str | None = None
    patient_name: str = Field(..., min_length=1, max_length=200)
    service_name: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., decimal_places=2, ge=0)
    doctor_id: str | None = None

    @field_validator("patient_name", "service_name", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class ShortBillUpdate(BaseModel):
    bill_date: date | None = None
    patient_id: str | None = None
    patient_name: str | None = Field(None, min_length=1, max_length=200)
    service_name: str | None = Field(None, min_length=1, max_length=200)
    amount: Decimal | None = Field(None, decimal_places=2, ge=0)
    doctor_id: str | None = None


class ShortBillRead(BaseModel):
    id: str
    bill_no: str
    bill_date: date
    short_bill_type_id: str
    short_bill_type_name: str | None = None
    patient_id: str | None
    patient_no: str | None = None
    patient_name: str
    service_name: str
    amount: Decimal
    doctor_id: str | None
    doctor_name: str | None = None

    model_config = {"from_attributes": True}


class ShortBillReportRow(BaseModel):
    serial_no: int
    bill_id: str
    bill_no: str
    bill_date: date
    patient_name: str
    amount: Decimal = Field(..., decimal_places=2)


class ShortBillReportRead(BaseModel):
    short_bill_type_id: str
    short_bill_type_name: str
    from_date: date
    to_date: date
    rows: list[ShortBillReportRow]
    grand_total: Decimal = Field(..., decimal_places=2)
