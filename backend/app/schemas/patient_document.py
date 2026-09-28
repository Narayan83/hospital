from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PatientDocumentCreate(BaseModel):
    patient_id: str
    document_date: date | None = None
    scanner_name: str | None = Field(None, max_length=200)
    remarks: str | None = None
    page_count: int = Field(default=1, ge=1)
    original_name: str | None = Field(None, max_length=255)


class PatientDocumentRead(ORMModel):
    id: str
    patient_id: str
    patient_no: str | None = None
    patient_name: str | None = None
    file_path: str
    original_name: str | None
    document_type: str
    page_count: int
    file_size_bytes: int
    scanner_name: str | None
    scanned_by_user_id: str | None
    scanned_by_name: str | None = None
    document_date: date
    remarks: str | None
    is_active: bool
    viewed_by_current_doctor: bool = False
    viewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PatientDocumentViewRead(ORMModel):
    id: str
    document_id: str
    doctor_id: str
    viewed_at: datetime
