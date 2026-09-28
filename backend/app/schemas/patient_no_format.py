from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.services.patient_number import PatientNumberGenerator


class PatientNoFormatCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=150)
    pattern: str = Field(..., min_length=3, max_length=100)
    sample_output: str = Field(..., min_length=1, max_length=50)
    seq_pad_width: int = Field(3, ge=0, le=10)
    is_selected: bool = False
    sort_order: int = 0
    is_active: bool = True

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        PatientNumberGenerator.validate_pattern(value.strip())
        return value.strip()


class PatientNoFormatUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    pattern: str | None = Field(None, min_length=3, max_length=100)
    sample_output: str | None = Field(None, min_length=1, max_length=50)
    seq_pad_width: int | None = Field(None, ge=0, le=10)
    is_selected: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return value
        PatientNumberGenerator.validate_pattern(value.strip())
        return value.strip()


class PatientNoFormatRead(ORMModel):
    id: str
    code: str
    name: str
    pattern: str
    sample_output: str
    seq_pad_width: int
    is_selected: bool
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
