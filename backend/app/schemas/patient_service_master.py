from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel


class PatientServiceMasterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    service_charge: Decimal = Field(default=Decimal("0"), ge=0)
    rate: Decimal = Field(default=Decimal("0"), ge=0)
    is_sharing: bool = False
    doctor_id: str | None = None
    show_in_doctor_collection: bool = False
    discount_apply: bool = False
    is_renewal: bool = False
    renewal_days: int | None = Field(None, ge=0, le=9999)
    category_id: str | None = None
    sub_category_id: str | None = None
    is_service_active: bool = True
    close_date: date | None = None

    @model_validator(mode="after")
    def validate_conditional_fields(self) -> "PatientServiceMasterBase":
        if self.is_sharing and not self.doctor_id:
            raise ValueError("Doctor is required when sharing is enabled")
        if not self.is_sharing:
            self.doctor_id = None
        if self.is_renewal and self.renewal_days is None:
            raise ValueError("Renewal days is required when renewal is enabled")
        if not self.is_renewal:
            self.renewal_days = None
        if not self.is_service_active and not self.close_date:
            raise ValueError("Close date is required when status is closed")
        if self.is_service_active:
            self.close_date = None
        return self


class PatientServiceMasterCreate(PatientServiceMasterBase):
    """Code is optional — blank/omitted values get the next number (e.g. PS101)."""

    code: str | None = Field(default=None, max_length=30)

    @field_validator("code", mode="before")
    @classmethod
    def blank_code_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value


class PatientServiceMasterUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    service_charge: Decimal | None = Field(None, ge=0)
    rate: Decimal | None = Field(None, ge=0)
    is_sharing: bool | None = None
    doctor_id: str | None = None
    show_in_doctor_collection: bool | None = None
    discount_apply: bool | None = None
    is_renewal: bool | None = None
    renewal_days: int | None = Field(None, ge=0, le=9999)
    category_id: str | None = None
    sub_category_id: str | None = None
    is_service_active: bool | None = None
    close_date: date | None = None


class PatientServiceMasterRead(ORMModel):
    id: str
    code: str
    name: str
    service_charge: Decimal
    rate: Decimal
    is_sharing: bool
    doctor_id: str | None
    doctor_name: str | None = None
    show_in_doctor_collection: bool = False
    category_id: str | None = None
    category_name: str | None = None
    sub_category_id: str | None = None
    sub_category_name: str | None = None
    discount_apply: bool
    is_renewal: bool
    renewal_days: int | None
    is_service_active: bool
    close_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("service_charge", "rate", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value
