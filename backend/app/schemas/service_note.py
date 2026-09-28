from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


def _normalize_code(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    # "0" is treated as the general (all-services) note, same as a blank code.
    if cleaned in ("", "0"):
        return None
    return cleaned


class ServiceNoteCreate(BaseModel):
    service_code: str | None = Field(None, max_length=30)
    note_text: str = Field(..., min_length=1)

    @field_validator("service_code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        return _normalize_code(value) if isinstance(value, str) or value is None else value


class ServiceNoteUpdate(BaseModel):
    service_code: str | None = Field(None, max_length=30)
    note_text: str | None = Field(None, min_length=1)
    is_active: bool | None = None

    @field_validator("service_code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        return _normalize_code(value) if isinstance(value, str) or value is None else value


class ServiceNoteRead(ORMModel):
    id: str
    service_code: str | None = None
    note_text: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
