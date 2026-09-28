from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class IpdAdmissionCreate(BaseModel):
    patient_id: str
    ward_id: str | None = None
    doctor_id: str | None = None
    department_id: str | None = None
    bed_no: str | None = Field(None, max_length=30)
    advance_amount: Decimal = Field(default=Decimal("0"), ge=0)
    diagnosis: str | None = Field(None, max_length=250)
    remarks: str | None = None
    admission_date: date | None = None


class IpdAdmissionRead(ORMModel):
    id: str
    admission_no: str
    admission_date: date
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
    advance_amount: Decimal
    diagnosis: str | None
    remarks: str | None
    status: str
    discharge_date: date | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("advance_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, value: object) -> object:
        if value is not None and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value
