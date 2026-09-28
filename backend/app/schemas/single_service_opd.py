from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SingleServiceOpdOptionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    service_id: str
    use_patient_id: bool = True
    default_rate: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    bill_prefix: str | None = Field(None, max_length=10)
    is_active: bool = True

    @field_validator("name", "bill_prefix", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class SingleServiceOpdOptionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    service_id: str | None = None
    use_patient_id: bool | None = None
    default_rate: Decimal | None = Field(None, ge=0, decimal_places=2)
    bill_prefix: str | None = Field(None, max_length=10)
    is_active: bool | None = None

    @field_validator("name", "bill_prefix", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class SingleServiceOpdOptionRead(BaseModel):
    id: str
    name: str
    menu_code: str
    service_id: str
    service_name: str
    use_patient_id: bool
    default_rate: Decimal
    bill_prefix: str
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class SingleServiceOpdBillCreate(BaseModel):
    option_id: str
    bill_date: date
    doctor_id: str
    patient_id: str | None = None
    patient_no: str | None = None
    patient_name: str = Field(default="", max_length=200)
    rate: Decimal = Field(..., ge=0, decimal_places=2)

    @field_validator("patient_name", "patient_no", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class SingleServiceOpdBillRead(BaseModel):
    id: str
    bill_no: str
    bill_date: date
    option_id: str
    option_name: str | None = None
    patient_id: str | None
    patient_no: str | None
    patient_name: str
    doctor_id: str
    doctor_name: str | None = None
    service_id: str | None
    service_name: str
    rate: Decimal
    payment_mode_name: str

    model_config = {"from_attributes": True}
