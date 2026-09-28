from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

SexCode = Literal["M", "F", "O", "U"]


def normalize_sex(value: str) -> str:
    mapping = {
        "m": "M",
        "f": "F",
        "o": "O",
        "u": "U",
        "male": "M",
        "female": "F",
        "other": "O",
        "unknown": "U",
    }
    normalized = mapping.get(value.strip().lower(), value.strip().upper())
    if normalized not in {"M", "F", "O", "U"}:
        raise ValueError("Sex must be M, F, O, or U")
    return normalized


class PatientBase(BaseModel):
    hospital_section_id: str | None = None
    facility: str | None = Field(None, max_length=150)
    title: str | None = Field(None, max_length=10)
    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    age: str | None = Field(None, max_length=20, description="e.g. '35 Years', '8 Months', '20 Days'")
    gender: str = Field(..., description="Sex code: M, F, O, or U")
    blood_group: str | None = Field(None, max_length=10)

    village_code: str | None = Field(None, max_length=20)
    contact_address1: str | None = Field(None, max_length=200)
    contact_address2: str | None = Field(None, max_length=200)
    contact_address3: str | None = Field(None, max_length=200)
    contact_address4: str | None = Field(None, max_length=200)
    contact_address5: str | None = Field(None, max_length=20)

    perm_address1: str | None = Field(None, max_length=200)
    perm_address2: str | None = Field(None, max_length=200)
    perm_address3: str | None = Field(None, max_length=200)
    perm_address4: str | None = Field(None, max_length=200)
    perm_address5: str | None = Field(None, max_length=20)

    old_software_id: str | None = Field(None, max_length=50)
    remarks: str | None = None
    phone: str | None = Field(None, max_length=20)
    mobile: str | None = Field(None, max_length=20)
    mobile2: str | None = Field(None, max_length=20)
    scheme: str | None = Field(None, max_length=100)
    aadhar_no: str | None = Field(None, max_length=20)
    is_existing_patient: bool = False
    patient_type: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        return normalize_sex(value)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    hospital_section_id: str | None = None
    facility: str | None = Field(None, max_length=150)
    title: str | None = Field(None, max_length=10)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    age: str | None = Field(None, max_length=20)
    gender: str | None = None
    blood_group: str | None = Field(None, max_length=10)

    village_code: str | None = Field(None, max_length=20)
    contact_address1: str | None = Field(None, max_length=200)
    contact_address2: str | None = Field(None, max_length=200)
    contact_address3: str | None = Field(None, max_length=200)
    contact_address4: str | None = Field(None, max_length=200)
    contact_address5: str | None = Field(None, max_length=20)

    perm_address1: str | None = Field(None, max_length=200)
    perm_address2: str | None = Field(None, max_length=200)
    perm_address3: str | None = Field(None, max_length=200)
    perm_address4: str | None = Field(None, max_length=200)
    perm_address5: str | None = Field(None, max_length=20)

    old_software_id: str | None = Field(None, max_length=50)
    remarks: str | None = None
    phone: str | None = Field(None, max_length=20)
    mobile: str | None = Field(None, max_length=20)
    mobile2: str | None = Field(None, max_length=20)
    scheme: str | None = Field(None, max_length=100)
    aadhar_no: str | None = Field(None, max_length=20)
    is_existing_patient: bool | None = None
    patient_type: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    is_active: bool | None = None

    @field_validator("gender", mode="before")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_sex(value)


class PatientNoPreview(BaseModel):
    patient_no: str
    format_code: str
    format_name: str
    pattern: str
    sample_output: str


class PatientSearchFilters(BaseModel):
    patient_no: str | None = Field(None, max_length=20)
    first_name: str | None = Field(None, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    village: str | None = Field(None, max_length=100)
    post: str | None = Field(None, max_length=100)
    taluk: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    mobile: str | None = Field(None, max_length=20)
    mobile2: str | None = Field(None, max_length=20)
    pin_code: str | None = Field(None, max_length=20)
    old_id: str | None = Field(None, max_length=50)
    aadhar_no: str | None = Field(None, max_length=20)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
    active_only: bool = False


class PatientRead(PatientBase, ORMModel):
    id: str
    patient_no: str
    hospital_section_name: str | None = None
    aadhar_scan_path: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
